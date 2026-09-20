# upwork-scraper

A personal job-hunting bot for blockchain/Web3 developers. Logs into Upwork, trawls through Best Matches and keyword-based search results across multiple pages, and drops everything into a local SQLite database. After each run it scores the haul against your personal filter rules and surfaces the gigs worth your time.

---

## How it works

Every run follows the same pipeline:

```
Authenticate → Build feed list → Scrape each feed → Store to DB → Filter & display
```

**Authenticate** — opens a dedicated Chrome profile. First run shows the login page; subsequent runs reuse the saved session. Google/Apple accounts and two-step verification are handled manually in the visible browser.

**Build feed list** — constructs a queue of URLs: the Best Matches page first, then one URL per (keyword × page) combination. With 12 default keywords and 5 pages each, that's 61 feeds per run.

**Scrape each feed** — scrolls each page to trigger lazy-loading, parses every job card for title, description, skill tags, proposal count, and client country. Only jobs that match at least one blockchain/Web3 signal are kept.

**Store to DB** — new jobs are inserted; existing ones get their proposal count and country refreshed. A commit fires every 25 writes so progress survives a crash mid-run.

**Filter & display** — reads `filter_config.json` and prints jobs that pass all your criteria: age cutoff, proposal ceiling, skill match, country exclusion, no full-time roles.

---

## Setup

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Google Chrome.

```bash
uv sync --locked
cp .env.example .env
```

Open `.env` and fill in your details:

```dotenv
UPWORK_USERNAME=you@example.com
UPWORK_PASSWORD=yourpassword        # omit for Google/Apple accounts

UPWORK_FIRST_NAME=Dhruv             # must match your Upwork profile exactly

UPWORK_SEARCH_QUERIES=              # comma-separated; leave blank for built-in list
UPWORK_SEARCH_PAGES=5               # pages per keyword (each page ≈ 10 jobs)
```

Everything else has a sensible default — see `.env.example` for the full list.

> `.env` is gitignored. Never commit it.

---

## Running

```bash
uv run upwork-scraper
```

Two lighter commands for sanity-checking:

```bash
uv run upwork-scraper --check-config    # validates settings + finds Chrome, no browser opens
uv run upwork-scraper --validate-login  # full login check, no scraping, no DB writes
```

One-off overrides (take effect for a single run only):

```
--database PATH             SQLite file location
--browser-path PATH         Chrome/Chromium executable
--proxy-server VALUE        http/https/socks4/socks5 proxy
--verification-timeout N    seconds to wait for manual verification
--log-level LEVEL           DEBUG | INFO | WARNING
```

---

## Default search keywords

When `UPWORK_SEARCH_QUERIES` is blank, the scraper searches Upwork for:

```
solidity · rust blockchain · smart contract developer · web3 developer
defi developer · ethereum developer · solana developer · trading bot crypto
mev bot · nft smart contract · blockchain developer · evm developer
```

Supply your own comma-separated list to override these entirely.

---

## Filter rules (`filter_config.json`)

Place this file in the project root. The scraper reads it at the end of every run.

```json
{
  "maxJobAge":   { "value": 24, "unit": "hours" },
  "proposals":   { "min": 1, "max": 20 },
  "skillsAndExpertise": {
    "matchAtLeast": 1,
    "anyOf": [
      "Blockchain", "Web3", "Solidity", "Smart Contract",
      "Solana", "Rust", "TypeScript", "Node.js", "NFT", "Cryptocurrency"
    ]
  },
  "excludeClientCountries": [
    "Philippines", "Pakistan", "Nigeria", "Bangladesh",
    "Sri Lanka", "Any African country"
  ],
  "jobType": ["fixed", "hourly"],
  "output": {
    "ifMissing": "mark as unknown and include the job, don't guess"
  }
}
```

| Rule | What it does |
|---|---|
| `maxJobAge` | Drops jobs posted before the cutoff |
| `proposals` | Drops jobs outside the min–max window |
| `skillsAndExpertise` | Job must hit at least `matchAtLeast` skills from `anyOf` (checked against tags, title, and description) |
| `excludeClientCountries` | Drops jobs whose scraped `client_country` is on the list. `"Any African country"` expands to a full continent list. Jobs with no country data are kept. |
| `jobType` | Full-time roles (detected from description text) are dropped unless `"fulltime"` is in the list |

---

## Database

Jobs land in `upwork_jobs.db` (SQLite). Schema:

| Column | Notes |
|---|---|
| `job_id` | Upwork URL cipher — primary deduplication key |
| `job_url` | Full job link |
| `job_title` | |
| `posted_date` | Converted from Upwork's relative timestamp |
| `job_description` | Full card text |
| `job_tags` | JSON array of skill tags |
| `job_proposals` | Raw Upwork text e.g. `"Fewer than 5"`, `"5 to 10"` |
| `client_country` | Parsed from the job card |
| `updated_at` | Last write timestamp |

---

## Scheduling

Each run is stateless — just launch it on a timer.

**Linux / macOS (cron, every 6 hours):**

```bash
0 */6 * * * cd /path/to/upwork-scraper && uv run upwork-scraper >> log/cron.log 2>&1
```

**Windows (Task Scheduler):**

Create a `.bat` file:

```bat
@echo off
cd /d "D:\path\to\upwork-scraper"
uv run upwork-scraper
```

Schedule it to repeat every 6 hours under your user account.

---

## Browser profile notes

The scraper keeps a dedicated Chrome profile separate from your everyday browser. Don't point `UPWORK_BROWSER_PROFILE_DIR` at your personal profile, don't share it, and don't run two scraper instances against the same profile at the same time.

---

## Disclaimer

This tool automates browsing that you would otherwise do manually. It does not submit applications, send messages, or make any changes to your Upwork account. Automated scraping may be in conflict with Upwork's Terms of Service — use it at your own discretion and risk.

---

## License

MIT — see [LICENSE](LICENSE).
