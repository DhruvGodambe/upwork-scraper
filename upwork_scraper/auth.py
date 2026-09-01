"""Upwork authentication workflow."""

from __future__ import annotations

import time
from collections.abc import Callable

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from .config import Settings

LOGIN_URL = "https://www.upwork.com/ab/account-security/login"
BEST_MATCHES_URL = "https://www.upwork.com/nx/find-work/best-matches"


def _visible_button(driver):
    for button in driver.find_elements(By.CSS_SELECTOR, "form#login button"):
        if (
            button.is_displayed()
            and button.is_enabled()
            and button.text.strip() in {"Continue", "Log in", "Sign in"}
        ):
            return button
    return None


def _click_submit(driver, field) -> None:
    button = _visible_button(driver)
    if button is not None:
        button.click()
    else:
        field.send_keys(Keys.ENTER)


def _authenticated(driver) -> bool:
    if "/account-security/login" in driver.current_url:
        return False
    return not any(e.is_displayed() for e in driver.find_elements(By.ID, "login_password"))


def _body_text(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def login(driver, settings: Settings, logger: Callable[[str], None]) -> None:
    driver.get(LOGIN_URL)
    username = WebDriverWait(driver, 30).until(
        lambda d: next(
            (e for e in d.find_elements(By.ID, "login_username") if e.is_displayed()), None
        )
    )
    username.clear()
    username.send_keys(settings.username)
    _click_submit(driver, username)

    try:
        password = WebDriverWait(driver, 30).until(
            lambda d: next(
                (e for e in d.find_elements(By.ID, "login_password") if e.is_displayed()), None
            )
        )
    except TimeoutException as exc:
        raise RuntimeError(f"Username step did not advance; page: {driver.current_url}") from exc

    password.clear()
    password.send_keys(settings.password)
    _click_submit(driver, password)

    deadline = time.monotonic() + settings.verification_timeout
    while time.monotonic() < deadline:
        if _authenticated(driver):
            driver.get(BEST_MATCHES_URL)
            return
        text = _body_text(driver).lower()
        if "technical difficulties" in text or "incorrect" in text:
            logger("Upwork displayed a login error; waiting for manual resolution")
        time.sleep(1)
    raise TimeoutException(
        f"Authentication did not complete within {settings.verification_timeout} seconds; "
        f"current URL: {driver.current_url}"
    )
