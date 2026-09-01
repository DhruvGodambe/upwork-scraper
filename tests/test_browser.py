from pathlib import Path

from upwork_scraper import browser
from upwork_scraper.browser import BrowserSpec


def test_browser_spec_extracts_major_version() -> None:
    spec = BrowserSpec(Path("/usr/bin/google-chrome"), "151.0.7922.173")
    assert spec.major_version == 151


def test_discovery_prefers_google_chrome(monkeypatch) -> None:
    monkeypatch.setattr(
        browser.shutil,
        "which",
        lambda name: {
            "google-chrome": "/opt/google/chrome/chrome",
            "chromium": "/snap/bin/chromium",
        }.get(name),
    )
    monkeypatch.setattr(browser, "_version", lambda path: "151.0.7922.173")

    spec = browser.discover_browser()

    assert spec.executable == Path("/opt/google/chrome/chrome")
    assert spec.major_version == 151
