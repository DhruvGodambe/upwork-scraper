from pathlib import Path

import pytest

from upwork_scraper.config import ConfigurationError, load_settings, validate_proxy_server


def test_load_settings_from_environment() -> None:
    settings = load_settings(
        {
            "UPWORK_USERNAME": "user@example.com",
            "UPWORK_PASSWORD": "secret",
            "UPWORK_FIRST_NAME": "FirstName",
            "UPWORK_DATABASE_PATH": "/tmp/jobs.db",
            "UPWORK_VERIFICATION_TIMEOUT": "45",
            "UPWORK_BROWSER_PROFILE_DIR": "/tmp/upwork-profile",
        }
    )
    assert settings.username == "user@example.com"
    assert settings.password == "secret"
    assert settings.database_path == Path("/tmp/jobs.db")
    assert settings.verification_timeout == 45
    assert settings.browser_profile_dir == Path("/tmp/upwork-profile")


def test_missing_credentials_fail_without_exposing_values() -> None:
    with pytest.raises(ConfigurationError, match="UPWORK_USERNAME and UPWORK_PASSWORD"):
        load_settings({})


def test_invalid_timeout_fails() -> None:
    with pytest.raises(ConfigurationError, match="must be an integer"):
        load_settings(
            {
                "UPWORK_USERNAME": "user@example.com",
                "UPWORK_PASSWORD": "secret",
                "UPWORK_FIRST_NAME": "FirstName",
                "UPWORK_VERIFICATION_TIMEOUT": "never",
            }
        )


def test_proxy_server_is_normalized_and_loaded() -> None:
    settings = load_settings(
        {
            "UPWORK_USERNAME": "user@example.com",
            "UPWORK_PASSWORD": "secret",
            "UPWORK_FIRST_NAME": "FirstName",
            "UPWORK_PROXY_SERVER": "127.0.0.1:1080",
        }
    )
    assert settings.proxy_server == "http://127.0.0.1:1080"


def test_proxy_server_rejects_embedded_credentials() -> None:
    with pytest.raises(ConfigurationError, match="must not contain proxy credentials"):
        validate_proxy_server("socks5://user:secret@127.0.0.1:1080")


def test_missing_profile_name_fails() -> None:
    with pytest.raises(ConfigurationError, match="UPWORK_FIRST_NAME must be set"):
        load_settings({"UPWORK_USERNAME": "user@example.com", "UPWORK_PASSWORD": "secret"})
