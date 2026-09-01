from upwork_scraper.auth import _authenticated, _login_warning, _visible_button


class FakeElement:
    def __init__(self, text="", displayed=True, enabled=True):
        self.text = text
        self._displayed = displayed
        self._enabled = enabled

    def is_displayed(self):
        return self._displayed

    def is_enabled(self):
        return self._enabled


class FakeDriver:
    def __init__(self, url, buttons=None, password_fields=None):
        self.current_url = url
        self.buttons = buttons or []
        self.password_fields = password_fields or []

    def find_elements(self, _by, selector):
        if selector == "form#login button":
            return self.buttons
        return self.password_fields


def test_visible_button_ignores_hidden_and_disabled_controls():
    driver = FakeDriver(
        "https://www.upwork.com/ab/account-security/login",
        buttons=[
            FakeElement("Continue", displayed=False),
            FakeElement("Continue", enabled=False),
            FakeElement("Continue"),
        ],
    )

    assert _visible_button(driver) is driver.buttons[2]


def test_authenticated_requires_leaving_login_page():
    login_driver = FakeDriver(
        "https://www.upwork.com/ab/account-security/login",
        password_fields=[FakeElement(displayed=False)],
    )
    authenticated_driver = FakeDriver(
        "https://www.upwork.com/nx/find-work/best-matches",
        password_fields=[],
    )

    assert not _authenticated(login_driver)
    assert _authenticated(authenticated_driver)


def test_login_warning_detects_security_interstitials():
    assert _login_warning("We detected abnormal behavior") == "abnormal behavior"
    assert _login_warning("The account has unusual activity") == "unusual activity"
    assert _login_warning("Normal login page") is None
