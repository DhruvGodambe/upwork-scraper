"""Backward-compatible entrypoint for the Upwork scraper."""

from upwork_scraper.app import main

if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
