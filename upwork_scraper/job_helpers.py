"""Helpers for identifying and parsing scraped Upwork jobs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import unquote

SEARCH_KEYWORDS: list[str] = [
    "solidity",
    "rust blockchain",
    "smart contract developer",
    "web3 developer",
    "defi developer",
    "ethereum developer",
    "solana developer",
    "trading bot crypto",
    "nft smart contract",
    "blockchain developer",
    "evm developer",
]


def build_search_url(query: str, page: int = 1) -> str:
    """Return an Upwork job-search URL for ``query``, sorted by recency."""
    from urllib.parse import urlencode
    params: dict = {"q": query, "sort": "recency"}
    if page > 1:
        params["page"] = page
    return "https://www.upwork.com/nx/search/jobs?" + urlencode(params)


BLOCKCHAIN_KEYWORDS: list[str] = [
    # Languages
    "rust",
    "solidity",
    # Blockchain / Web3 core
    "blockchain",
    "smart contract",
    "web3",
    "web 3",
    "defi",
    "decentralized",
    "dapp",
    "nft",
    "ethereum",
    "solana",
    "polkadot",
    "substrate",
    "cosmos",
    "avalanche",
    "cardano",
    "ton ",
    "near protocol",
    "layer 2",
    "layer2",
    "evm",
    "erc-20",
    "erc20",
    "erc-721",
    "erc721",
    "hardhat",
    "foundry",
    "anchor",
    "ethers.js",
    "ethers",
    "web3.js",
    "wagmi",
    "viem",
    "alchemy",
    "infura",
    "ipfs",
    "chainlink",
    "uniswap",
    "aave",
    "openzeppelin",
    # Crypto / trading bots
    "trading bot",
    "arbitrage",
    "mev",
    "sniper bot",
    "flash loan",
    "crypto bot",
    "dex",
    "liquidity",
    "yield farming",
    "staking",
    "mempool",
    "wallet",
    "cryptocurrency",
    "crypto",
    "token",
    "coin",
    "btc",
    "bitcoin",
    "exchange",
    # Bots (general, user explicitly requested)
    "bot",
    "automation bot",
    # JS/TS (user explicitly requested)
    "javascript",
    "typescript",
    "node.js",
    "nodejs",
    "react",
    "reactjs"
]


def is_relevant_job(title: str, description: str, tags: list[str]) -> bool:
    """Return True if the job matches any blockchain/relevant keyword."""
    haystack = " ".join([title, description, *tags]).lower()
    return any(kw in haystack for kw in BLOCKCHAIN_KEYWORDS)


def extract_job_id_from_url(url: str | None) -> str | None:
    """Extract the Upwork job cipher from a job URL."""

    if not url:
        return None
    match = re.search(r"_~([a-f0-9]+)", url)
    return match.group(1) if match else None


def extract_title_from_url(url: str | None) -> str | None:
    """Extract and clean the job title slug from a job URL."""

    if not url:
        return None
    try:
        path = url.split("/jobs/")[-1]
        slug = path.split("_~")[0]
        return unquote(slug.replace("-", " "))
    except Exception:
        return None


def generate_job_id(job_title: str, job_url: str | None = None, job_description: str = "") -> str:
    """Generate a stable job ID, preferring Upwork's URL cipher."""

    cipher = extract_job_id_from_url(job_url)
    if cipher:
        return cipher
    content = f"{job_title.lower()}|{job_description[:100].lower()}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def calculate_posted_datetime(timestamp: str) -> datetime:
    """Convert Upwork's relative timestamp into a local datetime."""

    now = datetime.now()
    t_lower = timestamp.lower()
    try:
        if "just now" in t_lower:
            return now
        if "yesterday" in t_lower:
            return now - timedelta(days=1)
        if "hour" in t_lower:
            return now - timedelta(hours=int(re.findall(r"\d+", timestamp)[0]))
        if "day" in t_lower:
            return now - timedelta(days=int(re.findall(r"\d+", timestamp)[0]))
        if "last week" in t_lower:
            return now - timedelta(weeks=1)
        if "week" in t_lower:
            return now - timedelta(weeks=int(re.findall(r"\d+", timestamp)[0]))
        if "minute" in t_lower:
            return now - timedelta(minutes=int(re.findall(r"\d+", timestamp)[0]))
    except (IndexError, ValueError):
        pass
    return now


def clean_job_proposals(job_proposals_text: str | None) -> str:
    """Normalize the proposals text shown on a job card."""

    if not job_proposals_text:
        return ""
    if "freelancers" in job_proposals_text:
        proposals = job_proposals_text.replace("Proposals: ", "").split(" Nu")[0]
    elif " ago" in job_proposals_text:
        proposals = ""
    else:
        proposals = (
            job_proposals_text.replace("Proposals: ", "")
            .replace("Load More Jobs", "")
            .replace("Featured", "")
        )
    return proposals.strip()


def clean_skills(skills: list[str]) -> list[str]:
    """Remove non-skill labels from the skills section."""

    exclude_list = {
        "more",
        "Next skills. Update list",
        "Skip skills",
        "  Payment verified",
        "  Payment unverified",
        "Skills",
        "Verified",
        "Payment verified",
        "Payment unverified",
    }
    cleaned = []
    for skill in skills:
        value = skill.strip()
        if not value or value in exclude_list:
            continue
        if "Rating is" in value or "$" in value:
            continue
        cleaned.append(value)
    return cleaned


_KNOWN_COUNTRIES = {
    "united states", "united kingdom", "canada", "australia", "germany",
    "france", "netherlands", "sweden", "norway", "denmark", "finland",
    "switzerland", "austria", "belgium", "italy", "spain", "portugal",
    "ireland", "new zealand", "singapore", "japan", "south korea",
    "israel", "uae", "united arab emirates", "saudi arabia", "qatar",
    "hong kong", "taiwan", "india", "china", "brazil", "mexico",
    "argentina", "colombia", "chile", "peru", "ukraine", "poland",
    "czech republic", "romania", "hungary", "bulgaria", "croatia",
    "turkey", "russia", "egypt", "south africa", "nigeria", "kenya",
    "ghana", "philippines", "pakistan", "bangladesh", "sri lanka",
    "indonesia", "malaysia", "vietnam", "thailand",
}


def extract_client_country(rows: list[str]) -> str:
    """Return the client country from job card rows, or empty string if not found."""
    for row in rows:
        val = row.strip().lower()
        if val in _KNOWN_COUNTRIES:
            return row.strip()
    return ""


def parse_job_details(rows: list[str], job_url: str | None = None) -> dict:
    """Parse one job card represented as a list of visible text lines."""

    if not rows:
        return {
            "posted_date": datetime.now(),
            "job_title": "",
            "job_description": "",
            "job_proposals": "",
            "job_tags": "[]",
            "job_id": generate_job_id("", job_url),
        }

    time_keywords = ["ago", "yesterday", "week", "day", "hour", "minute", "just now"]
    posted_date_text = next(
        (item for item in rows if any(keyword in item.lower() for keyword in time_keywords)),
        rows[0],
    )
    proposals_text = next((item for item in rows if "Proposals:" in item), "")
    description = max(rows, key=len)

    title = ""
    url_title_hint = extract_title_from_url(job_url)
    if url_title_hint:
        hint_words = set(url_title_hint.lower().split())
        for item in rows:
            value = item.strip()
            if not value or len(value) > 150:
                continue
            item_words = set(value.lower().split())
            if hint_words.issubset(item_words) or item_words.issubset(hint_words):
                title = value
                break

    if not title:
        title = next((item for item in rows if f"Job feedback {item}" in rows), "")

    if not title:
        blacklist = [
            "•",
            "more",
            "skills",
            "verified",
            "rating is",
            "payment",
            "save job",
            "job feedback",
            "proposals:",
            'about "',
        ]
        for item in rows:
            value = item.strip()
            value_lower = value.lower()
            if (
                value
                and not any(
                    value_lower == item or value_lower.startswith(item) for item in blacklist
                )
                and not any(keyword in value_lower for keyword in time_keywords)
                and len(value) < 150
            ):
                title = value
                break

    job_tags: list[str] = []
    try:
        skills_index = next(index for index, item in enumerate(rows) if item.strip() == "Skills")
        end_index = len(rows)
        for index in range(skills_index + 1, len(rows)):
            if any(
                marker in rows[index]
                for marker in ["Verified", "Payment", "Rating", "$", "United States"]
            ):
                end_index = index
                break
        job_tags = rows[skills_index + 1 : end_index]
    except StopIteration:
        pass

    return {
        "posted_date": calculate_posted_datetime(posted_date_text),
        "job_title": title,
        "job_description": description,
        "job_proposals": clean_job_proposals(proposals_text),
        "job_tags": json.dumps(clean_skills(job_tags)),
        "job_id": generate_job_id(title, job_url, description),
        "client_country": extract_client_country(rows),
    }
