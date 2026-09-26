"""Deterministic browser discovery and WebDriver startup."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
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
    # On Windows, chrome.exe --version opens the browser rather than printing to stdout.
    # Read the version from file metadata instead.
    if sys.platform == "win32":
        try:
            import ctypes
            fvi = ctypes.windll.version.GetFileVersionInfoSizeW(str(executable), None)
            if fvi:
                buf = ctypes.create_string_buffer(fvi)
                ctypes.windll.version.GetFileVersionInfoW(str(executable), None, fvi, buf)
                ver_ptr = ctypes.c_void_p()
                ver_len = ctypes.c_uint()
                ctypes.windll.version.VerQueryValueW(
                    buf, r"\StringFileInfo\040904B0\ProductVersion",
                    ctypes.byref(ver_ptr), ctypes.byref(ver_len)
                )
                version_str = ctypes.wstring_at(ver_ptr.value, ver_len.value - 1)
                match = re.search(r"(\d+(?:\.\d+){2,3})", version_str)
                if match:
                    return match.group(1)
        except Exception:
            pass
        # Fallback: version subdirectory name inside the Application folder
        app_dir = executable.parent
        for entry in app_dir.iterdir():
            if entry.is_dir() and re.match(r"\d+\.\d+\.\d+", entry.name):
                return entry.name
        raise BrowserError(f"Could not determine browser version from {executable}")

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

    # On Windows, Chrome is typically installed outside PATH.
    if sys.platform == "win32":
        win_candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for candidate_path in win_candidates:
            if candidate_path.is_file():
                return BrowserSpec(candidate_path, _version(candidate_path))

    raise BrowserError("No supported browser found; install Chrome or Chromium")


def _cached_driver_path(spec: BrowserSpec, cache_dir: Path) -> Path:
    return cache_dir / f"undetected-chromedriver-{spec.major_version}"


def _cache_driver(driver, destination: Path) -> None:
    source = Path(driver.patcher.executable_path)
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        with source.open("rb") as original:
            shutil.copyfileobj(original, temporary)
    temporary_path.chmod(0o755)
    temporary_path.replace(destination)


def _minimize_driver_window(driver) -> None:
    """Minimize the Chrome window owned by this driver without stealing focus."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        pid = driver.browser_pid
        SW_SHOWMINNOACTIVE = 7

        user32 = ctypes.windll.user32
        found: list[int] = []

        def _cb(hwnd: int, _: int) -> bool:
            if user32.IsWindowVisible(hwnd):
                proc_id = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                if proc_id.value == pid:
                    found.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(_cb), 0)
        for hwnd in found:
            user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
    except Exception:
        pass


def _launch_with_driver(settings: Settings, spec: BrowserSpec, driver_path: Path | None = None):
    options = uc.ChromeOptions()
    options.headless = False
    options.page_load_strategy = "eager"
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.user_data_dir = str(settings.browser_profile_dir)
    if settings.proxy_server:
        options.add_argument(f"--proxy-server={settings.proxy_server}")
    arguments = {
        "options": options,
        "browser_executable_path": str(spec.executable),
        "version_main": spec.major_version,
        "use_subprocess": True,
    }
    if driver_path is not None:
        arguments["driver_executable_path"] = str(driver_path)
    driver = uc.Chrome(**arguments)
    _minimize_driver_window(driver)
    return driver


def launch_driver(settings: Settings):
    spec = discover_browser(settings.browser_executable_path)
    cached_driver = _cached_driver_path(spec, settings.driver_cache_dir)
    if cached_driver.is_file():
        try:
            return _launch_with_driver(settings, spec, cached_driver), spec
        except Exception:
            # Keep the last known-good file. A fresh attempt may recover from a
            # stale driver, while a failed refresh must never erase the cache.
            pass

    try:
        driver = _launch_with_driver(settings, spec)
    except Exception as exc:
        raise BrowserError(
            f"Could not start ChromeDriver for browser major version {spec.major_version}. "
            "No usable cached driver was available; network access may be required for first setup."
        ) from exc
    _cache_driver(driver, cached_driver)
    return driver, spec
