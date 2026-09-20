<h1 align="center">Upwork Scraper</h1>
<h2 align="center">Python + Selenium + SQLite — Blockchain Job Hunter</h2>

---

Upwork Scraper performs authenticated scraping of Upwork job listings across multiple feeds and pages, filters results by relevance, and stores everything in a local SQLite database. Built for blockchain/Web3 developers looking for Solidity, Rust, Smart Contract, DeFi, and related gigs.

The browser remains visible so Upwork verification or two-factor authentication can be completed manually when required. SQLite is the only persistence format — no CSV exports.

---

## What It Does

1. **Authenticates** with your Upwork account using a persistent browser profile (reuses session across runs).
2. **Scrapes multiple feeds** in one run:
   - Best Matches feed
   - Keyword search feeds (e.g. `solidity`, `rust blockchain`, `web3 developer`, `mev bot`, etc.) across up to N pages each
3. **Filters for relevance** — only blockchain/Web3-related jobs (by title, description, and tags) are saved.
4. **Persists to SQLite** with deduplication by job ID. Commits every 25 new/updated jobs so no data is lost if the run is interrupted.
5. **Post-scrape filter** — after scraping, applies a `filter_config.json` rule set (proposals, job age, skill matching, country exclusion) and prints the top matching gigs.

---

## Key Features

- **Multi-feed scraping** — Best Matches + configurable keyword searches, each paginated up to N pages
- **Crash resilience** — each feed is independently wrapped; a dead ChromeDriver connection skips that feed instead of crashing the run
- **Partial commit safety** — periodic commits every 25 jobs + a final commit on clean exit or error
- **Client country capture** — country shown on the job card is parsed and stored per job
- **Post-scrape filter** — proposals range, max job age, skill matching, country exclusion, full-time job exclusion
- **Windows-compatible** — Chrome version read from file metadata; fallback discovery across `ProgramFiles`, `ProgramFiles(x86)`, and `LOCALAPPDATA`
- **Persistent browser profile** — completed logins and verifications are reused on later runs

---

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Google Chrome or Chromium

---

## Installation

```bash
uv sync --locked
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

`.env` must never be committed — it is gitignored.

```dotenv
UPWORK_USERNAME=your-email@example.com
UPWORK_PASSWORD=your-password          # leave empty for Google/Apple accounts

UPWORK_FIRST_NAME=YourFirstName        # must match your Upwork profile name

# Comma-separated search queries. Leave empty to use the built-in blockchain keyword list.
UPWORK_SEARCH_QUERIES=
# Pages to scrape per keyword search (default: 5)
UPWORK_SEARCH_PAGES=5

# Optional
UPWORK_DATABASE_PATH=upwork_jobs.db
BROWSER_EXECUTABLE_PATH=
UPWORK_PROXY_SERVER=
UPWORK_DRIVER_CACHE_DIR=~/.cache/upwork-scraper
UPWORK_BROWSER_PROFILE_DIR=~/.local/state/upwork-scraper/chrome-profile
UPWORK_VERIFICATION_TIMEOUT=120
LOG_LEVEL=INFO
```

**Notes:**
- `UPWORK_FIRST_NAME` is required — used to isolate the job results text during parsing.
- `UPWORK_PASSWORD` is optional. Leave it unset for Google/Apple-linked accounts and complete login manually in the visible browser.
- `UPWORK_SEARCH_QUERIES` — leave empty to use the built-in blockchain keyword list (`solidity`, `rust blockchain`, `smart contract developer`, `web3 developer`, `defi developer`, `ethereum developer`, `solana developer`, `trading bot crypto`, `mev bot`, `nft smart contract`, `blockchain developer`, `evm developer`).
- `UPWORK_SEARCH_PAGES` — number of search result pages scraped per keyword (default: 5). Each page is ~10 jobs.
- `UPWORK_PROXY_SERVER` accepts `http[s]://host:port`, `socks4://host:port`, `socks5://host:port`, or bare `host:port`.

---

## Post-Scrape Filter (`filter_config.json`)

After each scrape, the scraper reads `filter_config.json` from the project root and prints jobs that pass all criteria. Edit this file to tune your preferences:

```json
{
  "maxJobAge": { "value": 24, "unit": "hours" },
  "proposals": { "min": 1, "max": 20 },
  "skillsAndExpertise": {
    "matchAtLeast": 1,
    "anyOf": ["Blockchain", "Solidity", "Smart Contract", "Rust", "Web3", "Solana", "TypeScript", "Node.js"]
  },
  "excludeClientCountries": ["Philippines", "Pakistan", "Nigeria", "Bangladesh", "Sri Lanka", "Any African country"],
  "jobType": ["fixed", "hourly"],
  "output": {
    "ifMissing": "mark as unknown and include the job, don't guess"
  }
}
```

**Filter rules:**
| Field | Behaviour |
|---|---|
| `maxJobAge` | Excludes jobs older than N hours/days |
| `proposals` | Excludes jobs with proposal count outside the range |
| `skillsAndExpertise` | Job must match at least `matchAtLeast` skills from `anyOf` (checked against tags, title, and description) |
| `excludeClientCountries` | Excludes jobs where the scraped `client_country` matches. `"Any African country"` expands to a full list. Jobs with unknown country are included. |
| `jobType` | Full-time jobs (detected via title/description keywords) are excluded unless `"fulltime"` is listed |

---

## Usage

### Run a scrape

```bash
uv run upwork-scraper
```

This scrapes Best Matches + all keyword searches across up to `UPWORK_SEARCH_PAGES` pages each, saves results to SQLite, then prints the post-filter report.

### Validate config (no browser)

```bash
uv run upwork-scraper --check-config
```

### Validate login (no scrape)

```bash
uv run upwork-scraper --validate-login
```

Opens the browser, authenticates, and exits without touching the database. Useful for warming up the session before scheduling.

### CLI overrides (one run only)

| Flag | Description |
|---|---|
| `--database PATH` | Override SQLite database path |
| `--browser-path PATH` | Override Chrome/Chromium executable |
| `--proxy-server VALUE` | Override `UPWORK_PROXY_SERVER` |
| `--verification-timeout SECONDS` | Override manual verification window |
| `--log-level LEVEL` | Override log verbosity (`DEBUG`, `INFO`, `WARNING`) |

---

## How the Scraper Works

```
Login / session reuse
        │
        ▼
Build feed list:
  [Best Matches] + [keyword_1 p1..p5] + [keyword_2 p1..p5] + ...
        │
        ▼
For each feed URL:
  • Navigate → scroll → wait for jobs to load
  • Parse job cards (title, description, tags, proposals, client country)
  • Filter for blockchain relevance
  • INSERT new jobs / UPDATE existing ones
  • Commit every 25 new/updated jobs
  • On any error: log warning, skip feed, continue
        │
        ▼
Final DB commit
        │
        ▼
Apply filter_config.json → print top matches
```

### Database schema

Jobs are stored in `upwork_jobs.db` (SQLite):

| Column | Description |
|---|---|
| `job_id` | Upwork URL cipher — used for deduplication |
| `job_url` | Full job URL |
| `job_title` | Job title |
| `posted_date` | Parsed from Upwork's relative timestamp |
| `job_description` | Full description text from the card |
| `job_tags` | JSON array of skill tags |
| `job_proposals` | Proposal count text (e.g. `"Fewer than 5"`, `"5 to 10"`) |
| `client_country` | Country scraped from the job card |
| `updated_at` | Last time this row was written |

---

## Scheduling (cron / Task Scheduler)

### Linux/macOS — cron

Create `bin/launch_upwork_scraper.sh`:

```bash
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$(dirname "$DIR")"
nohup uv run upwork-scraper > /dev/null 2>&1 &
```

```bash
chmod +x bin/launch_upwork_scraper.sh
```

Add to crontab (every 6 hours):

```
0 */6 * * * /path/to/UpworkScraper/bin/launch_upwork_scraper.sh
```

### Windows — Task Scheduler

Create a `.bat` file:

```bat
@echo off
cd /d "D:\path\to\UpworkScraper"
uv run upwork-scraper
```

Schedule it via Task Scheduler to run every 6 hours.

---

## Browser Profile and Login Sessions

A dedicated persistent browser profile is used by default (`UPWORK_BROWSER_PROFILE_DIR`). On the first run the visible browser may ask for credentials, Google/Apple login, or two-step verification. Once authenticated, later runs reuse that session and open directly on Best Matches.

**Do not:**
- Share or commit the browser profile directory
- Point it at your personal Chrome profile
- Run multiple scraper processes against the same profile concurrently

---

## Disclaimer

This tool automates browsing of Upwork job listings to streamline a personal job search. Scraping Upwork may potentially conflict with their Terms of Service. Use responsibly, at your own discretion and risk. The author accepts no liability for misuse or legal consequences arising from its use.

---

## Contributing

Contributions are welcome. Open an issue or submit a pull request for bug reports and improvements.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
