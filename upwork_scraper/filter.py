"""Post-scrape job filter — applies user-defined criteria against the local DB."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_AFRICAN_COUNTRIES = [
    "nigeria", "kenya", "ghana", "ethiopia", "egypt", "south africa",
    "tanzania", "uganda", "cameroon", "senegal", "zimbabwe", "zambia",
    "mozambique", "angola", "ivory coast", "côte d'ivoire", "sudan",
    "somalia", "rwanda", "mali", "burkina faso", "malawi", "niger",
    "guinea", "benin", "togo", "liberia", "sierra leone", "botswana",
    "namibia", "gabon", "mauritius", "morocco", "algeria", "tunisia",
    "libya", "congo", "drc",
]

_FULLTIME_SIGNALS = [
    "full-time", "full time", "fulltime", "40+ hours", "40 hours/week",
    "40hrs", "permanent position", "long-term full", "time tracking",
]


@dataclass
class FilterConfig:
    skills: list[str] = field(default_factory=list)
    match_at_least: int = 1
    proposals_min: int = 0
    proposals_max: int = 50
    max_age_hours: int = 48
    excluded_countries: list[str] = field(default_factory=list)
    exclude_fulltime: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FilterConfig":
        skills_cfg = d.get("skillsAndExpertise", {})
        proposals_cfg = d.get("proposals", {})
        age_cfg = d.get("maxJobAge", {})
        age_val = age_cfg.get("value", 48)
        if age_cfg.get("unit", "hours").lower() == "days":
            age_val *= 24
        job_types = [t.lower() for t in d.get("jobType", [])]
        exclude_fulltime = "fulltime" not in job_types and "full-time" not in job_types
        return cls(
            skills=skills_cfg.get("anyOf", []),
            match_at_least=skills_cfg.get("matchAtLeast", 1),
            proposals_min=proposals_cfg.get("min", 0),
            proposals_max=proposals_cfg.get("max", 50),
            max_age_hours=int(age_val),
            excluded_countries=[c.lower() for c in d.get("excludeClientCountries", [])],
            exclude_fulltime=exclude_fulltime,
        )

    @classmethod
    def from_file(cls, path: Path) -> "FilterConfig":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _parse_proposal_bounds(text: str) -> tuple[int | None, int | None]:
    """Return (lower, upper) numeric bounds from Upwork proposal display text."""
    if not text:
        return None, None
    t = text.strip().lower()
    if "fewer than 5" in t:
        return 1, 4
    if "to" in t:
        nums = re.findall(r"\d+", t)
        if len(nums) == 2:
            return int(nums[0]), int(nums[1])
    if "+" in t:
        nums = re.findall(r"\d+", t)
        if nums:
            return int(nums[0]), None  # unbounded upper
    return None, None


def _proposals_in_range(text: str, min_p: int, max_p: int) -> bool:
    """Return True if the proposal text range overlaps [min_p, max_p]."""
    lower, upper = _parse_proposal_bounds(text)
    if lower is None:
        return True  # unknown — include per output rules
    if upper is None:
        return lower <= max_p
    # exclude if the entire range is above max or entirely below min
    return lower <= max_p and upper >= min_p


def _detect_country(title: str, description: str) -> str:
    """Best-effort country detection from title + description text."""
    haystack = (title + " " + description).lower()
    # Check explicit country names
    for phrase in [
        "philippines", "pakistan", "bangladesh", "sri lanka", "nigeria",
        *_AFRICAN_COUNTRIES,
    ]:
        if phrase in haystack:
            return phrase.title()
    return "unknown"


def _is_excluded_country(detected: str, excluded: list[str]) -> bool:
    d = detected.lower()
    for ex in excluded:
        ex_l = ex.lower()
        if ex_l == "any african country":
            if d in _AFRICAN_COUNTRIES:
                return True
        elif ex_l in d or d in ex_l:
            return True
    return False


def _is_fulltime(title: str, description: str) -> bool:
    haystack = (title + " " + description).lower()
    return any(sig in haystack for sig in _FULLTIME_SIGNALS)


def _matched_skills(title: str, description: str, tags_json: str, skill_list: list[str]) -> list[str]:
    """Match skills against tags, title, and description."""
    tags = {t.lower() for t in json.loads(tags_json or "[]")}
    haystack = (title + " " + description).lower()
    matched = []
    for s in skill_list:
        if s.lower() in tags or s.lower() in haystack:
            matched.append(s)
    return matched


def apply_filter(conn: sqlite3.Connection, config: FilterConfig) -> list[dict]:
    """Return jobs from ``conn`` that pass all applicable filter criteria."""
    cutoff = datetime.now() - timedelta(hours=config.max_age_hours)
    rows = conn.execute(
        "SELECT job_title, job_url, job_proposals, job_tags, posted_date, job_description, client_country "
        "FROM jobs WHERE posted_date >= ? ORDER BY posted_date DESC",
        (cutoff,),
    ).fetchall()

    results = []
    for title, url, proposals, tags_json, posted, description, db_country in rows:
        title = title or ""
        description = description or ""

        if config.exclude_fulltime and _is_fulltime(title, description):
            continue
        if not _proposals_in_range(proposals or "", config.proposals_min, config.proposals_max):
            continue
        matched = _matched_skills(title, description, tags_json or "[]", config.skills)
        if config.match_at_least > 0 and len(matched) < config.match_at_least:
            continue
        # Use DB country first; fall back to description-based detection
        detected_country = db_country.strip() if db_country and db_country.strip() else _detect_country(title, description)
        if config.excluded_countries and detected_country.lower() != "unknown" and _is_excluded_country(detected_country, config.excluded_countries):
            continue
        results.append(
            {
                "title": title or "unknown",
                "link": url or "unknown",
                "proposalCount": proposals or "unknown",
                "matchedSkills": matched or ["unknown"],
                "clientCountry": detected_country if detected_country else "unknown",
                "posted": posted,
            }
        )

    # Sort: fixed-price signals first (no "/hr" in title), then by recency
    def sort_key(j: dict):
        is_hourly = any(
            kw in (j["title"] + j.get("proposalCount", "")).lower()
            for kw in ["/hr", "hourly", "per hour"]
        )
        return (1 if is_hourly else 0, j["posted"])

    results.sort(key=sort_key, reverse=False)
    return results


def print_results(results: list[dict]) -> None:
    """Print filtered job results to stdout."""
    sep = "=" * 72
    if not results:
        print(f"\n{sep}")
        print("  FILTERED JOBS — 0 matches")
        print(f"{sep}\n")
        return

    print(f"\n{sep}")
    print(f"  FILTERED JOBS — {len(results)} match(es)")
    print("  Note: clientCountry / clientHistory / experienceLevel / jobType")
    print("        not scraped → shown as 'unknown'; jobs still included.")
    print(sep)
    for i, job in enumerate(results, 1):
        skills_str = ", ".join(job["matchedSkills"])
        print(f"\n[{i:>2}] {job['title']}")
        print(f"       Link:      {job['link']}")
        print(f"       Proposals: {job['proposalCount']}")
        print(f"       Skills:    {skills_str}")
        print(f"       Country:   {job['clientCountry']}")
        print(f"       Posted:    {job['posted']}")
    print(f"\n{sep}\n")
