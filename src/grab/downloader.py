"""
Downloader — unified yt-dlp wrapper for YouTube and Instagram.
Handles: video, audio, subtitles, carousel images, reels.
"""

import os
import re
import json
import time
import random
import logging
import requests
import yaml
from datetime import datetime
from typing import Optional, Dict, List

import yt_dlp

from grab.platform import find_ffmpeg, find_ffprobe

logger = logging.getLogger(__name__)

FFMPEG = find_ffmpeg()
FFPROBE = find_ffprobe()


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name or "untitled").strip()


def detect_platform(url: str) -> str:
    if "instagram.com" in url or "instagr.am" in url:
        return "instagram"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return "other"


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

def youtube_info(url: str) -> dict:
    opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _build_lang_fallbacks(lang: str) -> List[str]:
    norm = {"br": "pt-BR", "ptbr": "pt-BR", "pt_br": "pt-BR",
            "pt-pt": "pt-PT", "pt_pt": "pt-PT", "pt-br": "pt-BR"}
    lang = norm.get(lang.strip().lower(), lang) if lang else "pt"
    tries = [lang]
    if lang in ("pt", "pt-BR", "pt-PT"):
        for alt in ("pt-BR", "pt", "pt-PT"):
            if alt not in tries:
                tries.append(alt)
    return tries


def youtube_subtitle(url: str, output_dir: str, language: str = "pt",
                     cookie_file: Optional[str] = None) -> Dict:
    """Download subtitles via extract_info + direct HTTP (avoids yt-dlp format bugs)."""
    os.makedirs(output_dir, exist_ok=True)

    opts = {"quiet": True, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return {"success": False, "error": str(e)}

    langs = _build_lang_fallbacks(language)
    sub_url = sub_lang = sub_fmt = None

    for lc in langs:
        for source in ("subtitles", "automatic_captions"):
            subs = (info.get(source) or {}).get(lc)
            if not subs:
                continue
            for s in subs:
                if s.get("ext") in ("srt", "vtt", "json3"):
                    sub_url, sub_lang, sub_fmt = s["url"], lc, s["ext"]
                    break
            if sub_url:
                break
        if sub_url:
            break

    if not sub_url:
        return {"success": False, "error": "No subtitle found for requested languages",
                "title": info.get("title")}

    # Load cookies for request
    req_cookies = _load_cookies(cookie_file)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    content = _download_with_retry(sub_url, headers, req_cookies)
    if content is None:
        return {"success": False, "error": "Failed to download subtitle after retries",
                "title": info.get("title")}

    title_safe = sanitize_filename(info.get("title", "video"))
    raw_path = os.path.join(output_dir, f"{title_safe}.{sub_lang}.{sub_fmt}")
    with open(raw_path, "wb") as f:
        f.write(content)

    # Extract clean text
    text = _extract_subtitle_text(raw_path, sub_fmt)

    return {
        "success": True,
        "title": info.get("title"),
        "text": text,
        "subtitle_file": raw_path,
        "language": sub_lang,
        "info": {
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "thumbnail": info.get("thumbnail"),
            "url": url,
        },
    }


def youtube_media(url: str, output_dir: str, mode: str = "video",
                  quality: str = "1080p", audio_format: str = "mp3",
                  cookie_file: Optional[str] = None) -> Dict:
    """Download video or audio."""
    os.makedirs(output_dir, exist_ok=True)
    outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "ffmpeg_location": os.path.dirname(FFMPEG) or None,
    }

    if mode == "video":
        max_h = int(quality.replace("p", "")) if quality else 1080
        ydl_opts.update({
            "format": f"bestvideo[height<={max_h}]+bestaudio/best",
            "merge_output_format": "mp4",
        })
    elif mode == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": "0",
            }],
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if mode == "video":
                filepath = os.path.splitext(filepath)[0] + ".mp4"
            elif mode == "audio":
                filepath = os.path.splitext(filepath)[0] + f".{audio_format}"
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {
        "success": True,
        "title": info.get("title"),
        "media_path": filepath,
        "info": {
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "url": url,
        },
    }


# ---------------------------------------------------------------------------
# Instagram (yt-dlp fallback — not used by default, Playwright is primary)
# ---------------------------------------------------------------------------

def instagram_post(url: str, output_dir: str,
                   cookie_file: Optional[str] = None,
                   cookies_from_browser: Optional[str] = None) -> Dict:
    """
    Download an Instagram post: single image, carousel, reel, or video.
    Returns all media files + caption text.
    """
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": os.path.join(output_dir, "%(title)s_%(autonumber)03d.%(ext)s"),
        "writeinfojson": True,
        "writethumbnail": False,
    }

    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)
    elif cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        return {"success": False, "error": str(e)}

    # Collect all downloaded files
    media_files = []
    entries = info.get("entries") or [info]  # carousel = entries, single = just info

    for i, entry in enumerate(entries):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            filepath = ydl.prepare_filename(entry)
        # yt-dlp may produce .webp, .jpg, .mp4 etc
        base_no_ext = os.path.splitext(filepath)[0]
        # Find all files matching this base
        parent = os.path.dirname(filepath)
        base_name = os.path.basename(base_no_ext)
        for fname in os.listdir(parent):
            full = os.path.join(parent, fname)
            if fname.startswith(base_name) and not fname.endswith(".info.json"):
                if full not in media_files:
                    media_files.append(full)

    # Extract caption from info
    caption = info.get("description") or info.get("title") or ""
    uploader = info.get("uploader") or info.get("channel") or ""
    timestamp = info.get("timestamp")
    upload_date = info.get("upload_date")

    return {
        "success": True,
        "title": sanitize_filename(uploader or "instagram_post"),
        "caption": caption,
        "media_files": sorted(media_files),
        "media_count": len(media_files),
        "info": {
            "uploader": uploader,
            "timestamp": timestamp,
            "upload_date": upload_date,
            "url": url,
            "is_carousel": len(entries) > 1,
            "is_video": info.get("ext") in ("mp4", "webm") or info.get("vcodec") != "none",
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cookies(cookie_file: Optional[str]) -> dict:
    if not cookie_file or not os.path.exists(cookie_file):
        return {}
    cookies = {}
    try:
        with open(cookie_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
    except Exception:
        pass
    return cookies


def _download_with_retry(url: str, headers: dict, cookies: dict,
                         max_retries: int = 5) -> Optional[bytes]:
    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=30, cookies=cookies or None, headers=headers)
            if r.status_code == 429:
                cookies = {}  # drop cookies, try anonymous
                headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
                wait = min(2 ** (attempt + 1) + random.uniform(0, 2), 60)
                logger.warning("HTTP 429, retrying in %.1fs (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            if r.status_code == 200:
                return r.content
            logger.error("HTTP %d downloading subtitle", r.status_code)
            return None
        except requests.exceptions.Timeout:
            wait = min(2 ** attempt + random.uniform(0, 1), 30)
            logger.warning("Timeout, retrying in %.1fs", wait)
            time.sleep(wait)
        except Exception as e:
            logger.error("Download error: %s", e)
            return None
    return None


SRT_SEQ = re.compile(r"^\s*\d+\s*$")
TIMING_SRT = re.compile(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}")
TIMING_VTT = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}")
WEBVTT_HDR = re.compile(r"^\s*WEBVTT.*$", re.IGNORECASE)


def _extract_subtitle_text(path: str, fmt: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    if fmt == "json3":
        try:
            data = json.loads(raw)
            parts = []
            for ev in data.get("events", []):
                for seg in ev.get("segs", []):
                    t = seg.get("utf8", "").strip()
                    if t and t != "\n":
                        parts.append(t)
            return " ".join(parts)
        except Exception:
            return raw

    # SRT / VTT
    lines = raw.splitlines()
    out = []
    for line in lines:
        if WEBVTT_HDR.match(line) or SRT_SEQ.match(line):
            continue
        if TIMING_SRT.search(line) or TIMING_VTT.search(line):
            continue
        if line.strip():
            out.append(line.strip())
    return " ".join(out)
