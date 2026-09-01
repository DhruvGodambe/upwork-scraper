from pathlib import Path

from upwork_scraper import app
from upwork_scraper.browser import BrowserSpec
from upwork_scraper.config import Settings


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class FakeDriver:
    def __init__(self):
        self.closed = False

    def quit(self):
        self.closed = True


def test_validate_login_does_not_open_database(monkeypatch):
    settings = Settings(username="user@example.com", password="secret", first_name="FirstName")
    driver = FakeDriver()

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "_logger", lambda level: FakeLogger())
    monkeypatch.setattr(
        app,
        "launch_driver",
        lambda current: (driver, BrowserSpec(Path("/usr/bin/google-chrome"), "151.0.0")),
    )
    monkeypatch.setattr(app, "login", lambda *args: None)

    def unexpected_database_access(*args):
        raise AssertionError("login validation must not open the jobs database")

    monkeypatch.setattr(app, "connect_to_db", unexpected_database_access)

    assert app.main(["--validate-login"]) is True
    assert driver.closed is True


def test_cli_converts_success_to_zero(monkeypatch):
    monkeypatch.setattr(app, "main", lambda: True)

    assert app.cli() == 0


def test_cli_converts_failure_to_one(monkeypatch):
    monkeypatch.setattr(app, "main", lambda: False)

    assert app.cli() == 1
