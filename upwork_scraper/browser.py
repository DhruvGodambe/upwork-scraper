"""Deterministic browser discovery and WebDriver startup."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import undetected_chromedriver as uc  # type: ignore[import-untyped]

from .config import Settings


class BrowserError(RuntimeError):
    """Raised when a supported browser cannot be discovered or started."""


@dataclass(frozen=True)
class BrowserSpec:
    executable: Path
    version: str

    @property
    def major_version(self) -> int:
        return int(self.version.split(".", 1)[0])


def _version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True, check=False
    )
    match = re.search(r"(\d+(?:\.\d+){2,3})", result.stdout + result.stderr)
    if not match:
        raise BrowserError(f"Could not determine browser version from {executable}")
    return match.group(1)


def discover_browser(explicit_path: str | None = None) -> BrowserSpec:
    if explicit_path:
        executable = Path(explicit_path).expanduser()
        if not executable.is_file() or not executable.stat().st_mode & 0o111:
            raise BrowserError(f"Browser executable is not executable: {executable}")
        return BrowserSpec(executable, _version(executable))

    # Keep this ordered list deliberate. The dependency currently searches PATH
    # using an unordered set, which is unsafe when both browsers are installed.
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            # Preserve snap wrappers such as /snap/bin/chromium; resolving them
            # would turn the browser path into /usr/bin/snap.
            executable = Path(path)
            return BrowserSpec(executable, _version(executable))
    raise BrowserError("No supported browser found; install Chrome or Chromium")


def launch_driver(settings: Settings):
    spec = discover_browser(settings.browser_executable_path)
    options = uc.ChromeOptions()
    options.headless = False
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(
        options=options,
        browser_executable_path=str(spec.executable),
        version_main=spec.major_version,
        use_subprocess=True,
    )
    return driver, spec
