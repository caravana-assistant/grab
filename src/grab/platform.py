"""Auto-detect platform-specific paths for ffmpeg, Chrome, etc."""

import os
import shutil
import sys

_IS_MAC = sys.platform == "darwin"
_IS_LINUX = sys.platform.startswith("linux")


def find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    candidates = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return "ffmpeg"


def find_ffprobe() -> str:
    path = shutil.which("ffprobe")
    if path:
        return path
    candidates = ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return "ffprobe"


def find_chrome() -> str:
    if _IS_MAC:
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(mac_path):
            return mac_path

    if _IS_LINUX:
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            path = shutil.which(name)
            if path:
                return path

    # Windows / fallback
    path = shutil.which("google-chrome") or shutil.which("chrome")
    if path:
        return path

    return "google-chrome"


def find_chrome_profile() -> str:
    if _IS_MAC:
        return os.path.expanduser("~/Library/Application Support/Google/Chrome/Default")
    if _IS_LINUX:
        return os.path.expanduser("~/.config/google-chrome/Default")
    # Windows
    return os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/Default")


def default_output_dir() -> str:
    return os.path.expanduser("~/grab-output")


def default_cookie_file() -> str:
    return os.path.expanduser("~/.config/grab/youtube_cookies.txt")
