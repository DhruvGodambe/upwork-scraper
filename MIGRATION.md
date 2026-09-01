# Migration guide

## From the 1.x project layout to 2.0

Version 2.0 modernizes configuration, packaging, browser startup, and development tooling.

### Installation

Install [uv](https://docs.astral.sh/uv/) and recreate the project environment:

```bash
uv sync --locked
```

`requirements.txt` is no longer provided. `uv.lock` and `pyproject.toml` are the authoritative
dependency files.

### Configuration

Copy the example environment file and set your own credentials:

```bash
cp .env.example .env
```

Set `UPWORK_USERNAME`, `UPWORK_PASSWORD`, and `UPWORK_USER_NAME` in `.env`. The latter is the
first name shown in the Upwork profile panel and is currently required to isolate job text. The
legacy `settings/config.py` file is
no longer read and must not be used for credentials. Never commit `.env` or any file containing
real credentials.

### Running the application

Use the packaged command for normal operation:

```bash
uv run upwork-scraper
```

The legacy root command remains available for compatibility:

```bash
uv run python upwork_best_matches_scraper.py
```

Before the first scrape, validate the local browser and account setup:

```bash
uv run upwork-scraper --check-config
uv run upwork-scraper --validate-login
```

### Python imports

Database and parsing modules now live under the application package:

```python
from upwork_scraper.database import connect_to_db, create_db
from upwork_scraper.job_helpers import parse_job_details
```

The old `utils` package is no longer included.

### Data and browser state

SQLite remains the supported storage format. Existing SQLite databases can be reused with
`UPWORK_DATABASE_PATH`; CSV dumps are not imported or generated.

The scraper now uses a dedicated persistent browser profile by default. Do not point it at a
personal Chrome/Chromium profile, and do not run multiple scraper processes against the same
profile simultaneously.
