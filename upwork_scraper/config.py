"""Typed runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    username: str
    password: str = field(repr=False)
    user_name: str | None = None
    browser_executable_path: str | None = None
    driver_cache_dir: Path = Path.home() / ".cache" / "upwork-scraper"
    browser_profile_dir: Path = (
        Path.home() / ".local" / "state" / "upwork-scraper" / "chrome-profile"
    )
    database_path: Path = Path("upwork_jobs.db")
    verification_timeout: int = 120
    log_level: str = "INFO"


def _env(name: str, environ: Mapping[str, str]) -> str | None:
    value = environ.get(name)
    return value.strip() if value else None


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load settings, with process environment taking precedence over ``.env``."""

    load_dotenv()
    values = os.environ if environ is None else environ
    username = _env("UPWORK_USERNAME", values)
    password = _env("UPWORK_PASSWORD", values)
    if not username or not password:
        raise ConfigurationError(
            "UPWORK_USERNAME and UPWORK_PASSWORD must be set in the environment or .env"
        )

    timeout_text = _env("UPWORK_VERIFICATION_TIMEOUT", values) or "120"
    try:
        verification_timeout = int(timeout_text)
    except ValueError as exc:
        raise ConfigurationError("UPWORK_VERIFICATION_TIMEOUT must be an integer") from exc
    if verification_timeout <= 0:
        raise ConfigurationError("UPWORK_VERIFICATION_TIMEOUT must be greater than zero")

    return Settings(
        username=username,
        password=password,
        user_name=_env("UPWORK_USER_NAME", values),
        browser_executable_path=_env("BROWSER_EXECUTABLE_PATH", values),
        driver_cache_dir=Path(
            _env("UPWORK_DRIVER_CACHE_DIR", values) or Path.home() / ".cache" / "upwork-scraper"
        ).expanduser(),
        browser_profile_dir=Path(
            _env("UPWORK_BROWSER_PROFILE_DIR", values)
            or Path.home() / ".local" / "state" / "upwork-scraper" / "chrome-profile"
        ).expanduser(),
        database_path=Path(_env("UPWORK_DATABASE_PATH", values) or "upwork_jobs.db"),
        verification_timeout=verification_timeout,
        log_level=(_env("LOG_LEVEL", values) or "INFO").upper(),
    )
