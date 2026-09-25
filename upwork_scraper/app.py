"""Application orchestration."""

from __future__ import annotations

import json
import logging
import sys
import random
import time
from argparse import ArgumentParser
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .auth import BEST_MATCHES_URL, login
from .browser import discover_browser, launch_driver
from .config import ConfigurationError, Settings, load_settings, validate_proxy_server
from .database import connect_to_db, create_db
from .filter import FilterConfig, apply_filter, print_results
from .job_helpers import SEARCH_KEYWORDS, build_best_matches_url, build_search_url, is_relevant_job, parse_job_details

SCROLL_STEPS = 12
SCROLL_PAUSE_SECONDS = 0.5
JOB_COUNT_STABLE_POLLS = 3
JOB_COUNT_STABLE_TIMEOUT = 30


@dataclass(frozen=True)
class ScrapeCounts:
    """Database outcomes for one scrape run."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def processed(self) -> int:
        return self.inserted + self.updated + self.unchanged + self.failed

    def __add__(self, other: "ScrapeCounts") -> "ScrapeCounts":
        return ScrapeCounts(
            inserted=self.inserted + other.inserted,
            updated=self.updated + other.updated,
            unchanged=self.unchanged + other.unchanged,
            failed=self.failed + other.failed,
            skipped=self.skipped + other.skipped,
        )


def _logger(level: str) -> logging.Logger:
    logger = logging.getLogger("upwork_scraper")
    logger.setLevel(getattr(logging, level, logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        log_dir = Path(__file__).resolve().parents[1] / "log"
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "upwork_best_matches_scraper.log")
        file_handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s %(message)s"))
        logger.addHandler(file_handler)
    return logger


def _arguments(argv: list[str] | None):
    parser = ArgumentParser(description="Scrape Upwork Best Matches once")
    parser.add_argument("--check-config", action="store_true", help="validate settings and browser")
    parser.add_argument("--database", help="SQLite database path")
    parser.add_argument("--browser-path", help="browser executable path")
    parser.add_argument("--proxy-server", help="proxy URL or host:port")
    parser.add_argument(
        "--validate-login",
        action="store_true",
        help="validate live Upwork login without scraping or writing jobs",
    )
    parser.add_argument("--verification-timeout", type=int)
    parser.add_argument("--log-level")
    return parser.parse_args(argv)


def _job_urls(driver) -> list[str]:
    hrefs = driver.execute_script(
        "return Array.from(document.querySelectorAll(\"a[href*='/jobs/']\"), link => link.href);"
    )
    return [href.split("?", 1)[0].rstrip("/") for href in hrefs if "ontology_skill_uid" not in href]


def _feed_container(driver):
    """Return the scrollable job-feed container, falling back to window scroll."""

    return driver.execute_script(
        """
        const candidates = Array.from(document.querySelectorAll('div, main, section'))
          .filter(n => n.scrollHeight > n.clientHeight + 100 && n.clientHeight > 300);
        if (!candidates.length) return null;
        candidates.sort((a, b) => b.scrollHeight - a.scrollHeight);
        return candidates[0];
        """
    )


def _scroll_feed(driver, container) -> None:
    """Send a real mouse-wheel event; synthesized scrollTop does not trigger
    the feed's lazy loader, but Chromium's wheel input does."""

    if container is None:
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        return
    rect = driver.execute_script(
        "const r = arguments[0].getBoundingClientRect();"
        "return {x: r.x + r.width / 2, y: Math.max(r.y + r.height / 2, 0)};",
        container,
    )
    driver.execute_cdp_cmd(
        "Input.dispatchMouseEvent",
        {"type": "mouseWheel", "x": rect["x"], "y": rect["y"], "deltaX": 0, "deltaY": 600},
    )


def _load_job_list(driver, logger: logging.Logger) -> None:
    """Scroll through results and wait briefly for lazy-loaded jobs to settle."""

    container = _feed_container(driver)
    for step in range(1, SCROLL_STEPS + 1):
        _scroll_feed(driver, container)
        time.sleep(SCROLL_PAUSE_SECONDS)
        logger.info(
            "Loading jobs: scroll %d/%d; %d job links visible",
            step,
            SCROLL_STEPS,
            len(_job_urls(driver)),
        )

    if container is not None:
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
    else:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    WebDriverWait(driver, 120).until(EC.visibility_of_element_located((By.TAG_NAME, "footer")))
    previous_count = -1
    stable_polls = 0

    def stable_job_count(current_driver) -> bool:
        nonlocal previous_count, stable_polls
        current_count = len(_job_urls(current_driver))
        if current_count == previous_count:
            stable_polls += 1
        else:
            previous_count = current_count
            stable_polls = 1
        return stable_polls >= JOB_COUNT_STABLE_POLLS

    WebDriverWait(driver, JOB_COUNT_STABLE_TIMEOUT, poll_frequency=1).until(stable_job_count)
    logger.info("Job list loaded: %d job links visible", previous_count)


PERIODIC_COMMIT_EVERY = 25


def _process_jobs(job_posts: list[str], job_urls: list[str], cursor, conn, logger) -> ScrapeCounts:
    """Parse and persist posts, retaining progress when one post fails."""

    if len(job_posts) != len(job_urls):
        logger.warning(
            "Job result mismatch: %d parsed posts and %d job links; processing %d pairs",
            len(job_posts),
            len(job_urls),
            min(len(job_posts), len(job_urls)),
        )

    inserted = 0
    updated = 0
    unchanged = 0
    failed = 0
    skipped = max(0, len(job_posts) - len(job_urls))  # mismatch + filtered
    processable = min(len(job_posts), len(job_urls))
    age_cutoff = datetime.now() - timedelta(hours=48)
    for index in range(processable):
        post = job_posts[index]
        try:
            details = parse_job_details(post.split("\n"), job_url=job_urls[index])
            tags: list[str] = json.loads(details.get("job_tags") or "[]")
            if not is_relevant_job(details["job_title"], details["job_description"], tags):
                skipped += 1
                logger.debug("Skipped irrelevant job: %s", details["job_title"])
                continue
            # Skip jobs older than 48 hours at scrape time
            if details["posted_date"] < age_cutoff:
                skipped += 1
                logger.debug("Skipped stale job (>48h): %s", details["job_title"])
                continue
            cursor.execute(
                "SELECT job_proposals, updated_at FROM jobs WHERE job_id = ?", (details["job_id"],)
            )
            existing = cursor.fetchone()
            if existing is not None:
                stored_proposals = existing[0] or ""
                scraped_proposals = details["job_proposals"] or ""
                new_country = details.get("client_country", "")
                # Always update country; also update proposals if changed
                cursor.execute(
                    "UPDATE jobs SET job_proposals = ?, client_country = ?, updated_at = ? WHERE job_id = ?",
                    (scraped_proposals, new_country, datetime.now(), details["job_id"]),
                )
                if stored_proposals == scraped_proposals:
                    unchanged += 1
                else:
                    updated += 1
                continue
            else:
                cursor.execute(
                    "INSERT INTO jobs (job_id, job_url, job_title, posted_date, "
                    "job_description, job_tags, job_proposals, client_country) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        details["job_id"],
                        job_urls[index],
                        details["job_title"],
                        details["posted_date"],
                        details["job_description"],
                        details["job_tags"],
                        details["job_proposals"],
                        details.get("client_country", ""),
                    ),
                )
                inserted += 1
        except Exception as exc:
            failed += 1
            logger.warning("Job %d/%d failed: %s", index + 1, processable, exc)
        if (index + 1) % 5 == 0 or index + 1 == processable:
            logger.info(
                "Processed %d/%d jobs (%d inserted, %d updated, %d unchanged, %d failed)",
                index + 1,
                len(job_posts),
                inserted,
                updated,
                unchanged,
                failed,
            )
        if (inserted + updated) > 0 and (inserted + updated) % PERIODIC_COMMIT_EVERY == 0:
            conn.commit()
            logger.info("Periodic commit: %d jobs saved so far", inserted + updated)
    return ScrapeCounts(inserted, updated, unchanged, failed, skipped)


def _is_dead_session(exc: Exception) -> bool:
    """Return True when the exception means Chrome is gone and needs a restart."""
    return isinstance(exc, (InvalidSessionIdException, NoSuchWindowException)) or (
        isinstance(exc, WebDriverException)
        and any(
            phrase in str(exc)
            for phrase in ("invalid session id", "no such window", "disconnected", "not connected to DevTools")
        )
    )


def _scrape_feed(
    driver, url: str, settings: Settings, cursor, conn, logger: logging.Logger
) -> ScrapeCounts:
    """Navigate to ``url``, scroll the job feed, and persist matching jobs.

    Any exception (including a ChromeDriver connection timeout after a long
    session) is caught here so one failed feed skips rather than crashing
    the entire run.
    """
    logger.info("Scraping feed: %s", url)
    try:
        driver.get(url)

        try:
            WebDriverWait(driver, 30).until(lambda d: len(_job_urls(d)) > 0)
        except TimeoutException:
            logger.warning("No job links found at %s — skipping", url)
            return ScrapeCounts()

        _load_job_list(driver, logger)

        try:
            containers = WebDriverWait(driver, 30).until(
                EC.presence_of_all_elements_located((By.XPATH, "//main/div"))
            )
        except TimeoutException:
            logger.warning("Could not locate job container at %s — skipping", url)
            return ScrapeCounts()

        text = containers[-1].text
        if settings.first_name and settings.first_name in text:
            text = text.split(settings.first_name)[0]
        for marker in ("Ordered by most relevant.", "Ordered by newest.", "Ordered by"):
            if marker in text:
                text = text.split(marker, 1)[-1]
                break
        job_posts = text.split("Posted")[1:]
        job_urls = _job_urls(driver)
        logger.info("Parsed %d job posts and found %d job links", len(job_posts), len(job_urls))
        return _process_jobs(job_posts, job_urls, cursor, conn, logger)

    except Exception as exc:
        if _is_dead_session(exc):
            raise
        logger.warning("Feed %s failed (%s: %s) — skipping", url, type(exc).__name__, exc)
        return ScrapeCounts()


def main(argv: list[str] | None = None) -> bool:
    args = _arguments(argv)
    try:
        settings = load_settings()
        if args.database:
            settings = replace(settings, database_path=Path(args.database))
        if args.browser_path:
            settings = replace(settings, browser_executable_path=args.browser_path)
        if args.proxy_server:
            settings = replace(settings, proxy_server=validate_proxy_server(args.proxy_server))
        if args.verification_timeout is not None:
            if args.verification_timeout <= 0:
                raise ConfigurationError("--verification-timeout must be greater than zero")
            settings = replace(settings, verification_timeout=args.verification_timeout)
        if args.log_level:
            settings = replace(settings, log_level=args.log_level.upper())
        logger = _logger(settings.log_level)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return False

    if args.check_config:
        try:
            browser = discover_browser(settings.browser_executable_path)
            print(f"Configuration is valid; browser={browser.executable} version={browser.version}")
            return True
        except Exception as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return False

    if args.validate_login:
        driver = None
        try:
            driver, browser = launch_driver(settings)
            logger.info("Using %s (%s)", browser.executable, browser.version)
            logger.info("Validating Upwork login")
            login(driver, settings, lambda message: logger.warning(message))
            logger.info("Upwork login validation succeeded")
            return True
        except Exception:
            logger.exception("Login validation failed")
            return False
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    logger.warning("Browser was already closed")

    conn, cursor = connect_to_db(settings.database_path)
    driver = None
    try:
        create_db(conn, cursor)
        driver, browser = launch_driver(settings)
        logger.info("Using %s (%s)", browser.executable, browser.version)
        logger.info("Checking Upwork authentication")
        login(driver, settings, lambda message: logger.warning(message))
        logger.info("Upwork authentication ready")

        # High-yield keywords get full pages; low-yield ones get 2 pages max
        _HIGH_YIELD = {"solidity", "smart contract developer", "blockchain developer", "web3 developer"}
        search_queries = settings.search_queries if settings.search_queries else SEARCH_KEYWORDS
        # Build feed list as (url, is_same_keyword_continuation) tuples for smart delay
        _best_match_feeds = [(build_best_matches_url(p), p > 1) for p in range(1, settings.search_pages + 1)]
        _keyword_feeds = []
        for q in search_queries:
            pages = settings.search_pages if q in _HIGH_YIELD else min(2, settings.search_pages)
            _keyword_feeds += [(build_search_url(q, page=p), p > 1) for p in range(1, pages + 1)]
        _all_feeds = _best_match_feeds + _keyword_feeds
        feed_urls = [url for url, _ in _all_feeds]
        logger.info(
            "Running %d feed(s): Best Matches × %d page(s) + %d keyword search(es)",
            len(feed_urls),
            settings.search_pages,
            len(search_queries),
        )

        total = ScrapeCounts()
        for feed_url, is_continuation in _all_feeds:
            try:
                total = total + _scrape_feed(driver, feed_url, settings, cursor, conn, logger)
            except Exception as exc:
                if not _is_dead_session(exc):
                    raise
                logger.warning("Chrome session lost (%s) — restarting browser", type(exc).__name__)
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
                conn.commit()
                logger.info("Progress committed before browser restart")
                driver, _ = launch_driver(settings)
                login(driver, settings, lambda message: logger.warning(message))
                logger.info("Browser restarted and re-authenticated — resuming from %s", feed_url)
                try:
                    total = total + _scrape_feed(driver, feed_url, settings, cursor, conn, logger)
                except Exception as retry_exc:
                    logger.warning(
                        "Feed %s failed after restart (%s) — skipping", feed_url, retry_exc
                    )
            # Short delay between pages of the same keyword; longer when switching
            delay = random.uniform(2, 4) if is_continuation else random.uniform(6, 10)
            logger.info("Waiting %.1fs before next feed...", delay)
            time.sleep(delay)

        conn.commit()
        logger.info(
            "All feeds complete: %d inserted, %d updated, %d unchanged, %d failed, "
            "%d skipped; database commit succeeded",
            total.inserted,
            total.updated,
            total.unchanged,
            total.failed,
            total.skipped,
        )

        filter_cfg_path = Path(__file__).resolve().parents[1] / "filter_config.json"
        if filter_cfg_path.is_file():
            try:
                cfg = FilterConfig.from_file(filter_cfg_path)
                results = apply_filter(conn, cfg)
                print_results(results)
            except Exception as exc:
                logger.warning("Filter step failed: %s", exc)

        return True
    except Exception:
        logger.exception("Scraping failed")
        try:
            conn.commit()
            logger.info("Partial work committed to database before exit")
        except Exception:
            pass
        return False
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        cursor.close()
        conn.close()


def cli() -> int:
    """Run the packaged command with conventional process exit statuses."""

    return 0 if main() else 1
