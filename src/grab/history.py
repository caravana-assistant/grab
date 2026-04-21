"""
Track extracted URLs to avoid duplicates.
Stores a history.json in the output directory.
"""

import json
import os
import re
from datetime import datetime
from typing import Optional


HISTORY_FILE = "history.json"


def _normalize_url(url: str) -> str:
    """Normalize URL for dedup — strip tracking params, trailing slashes."""
    url = url.split("?")[0].rstrip("/")
    # YouTube: extract video ID
    yt_match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    if yt_match:
        return f"youtube:{yt_match.group(1)}"
    # Instagram: extract shortcode
    ig_match = re.search(r"instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)", url)
    if ig_match:
        return f"instagram:{ig_match.group(1)}"
    return url


def _load(output_dir: str) -> dict:
    path = os.path.join(output_dir, HISTORY_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"extractions": []}


def _save(output_dir: str, data: dict):
    path = os.path.join(output_dir, HISTORY_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_duplicate(output_dir: str, url: str) -> Optional[dict]:
    """Return the existing extraction entry if URL was already grabbed, else None."""
    key = _normalize_url(url)
    data = _load(output_dir)
    for entry in data["extractions"]:
        if entry.get("key") == key:
            return entry
    return None


def record(output_dir: str, url: str, title: str, folder: str, platform: str):
    """Record a successful extraction."""
    data = _load(output_dir)
    data["extractions"].append({
        "key": _normalize_url(url),
        "url": url,
        "title": title,
        "folder": folder,
        "platform": platform,
        "date": datetime.now().isoformat(),
    })
    _save(output_dir, data)
