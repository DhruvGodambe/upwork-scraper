from pathlib import Path

import pytest

from upwork_scraper.config import ConfigurationError, load_settings


def test_load_settings_from_environment() -> None:
    settings = load_settings(
        {
            "UPWORK_USERNAME": "user@example.com",
            "UPWORK_PASSWORD": "secret",
            "UPWORK_DATABASE_PATH": "/tmp/jobs.db",
            "UPWORK_VERIFICATION_TIMEOUT": "45",
        }
    )
    assert settings.username == "user@example.com"
    assert settings.password == "secret"
    assert settings.database_path == Path("/tmp/jobs.db")
    assert settings.verification_timeout == 45


def test_missing_credentials_fail_without_exposing_values() -> None:
    with pytest.raises(ConfigurationError, match="UPWORK_USERNAME and UPWORK_PASSWORD"):
        load_settings({})


def test_invalid_timeout_fails() -> None:
    with pytest.raises(ConfigurationError, match="must be an integer"):
        load_settings(
            {
                "UPWORK_USERNAME": "user@example.com",
                "UPWORK_PASSWORD": "secret",
                "UPWORK_VERIFICATION_TIMEOUT": "never",
            }
        )
