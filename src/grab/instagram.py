"""
Instagram downloader via Playwright — uses Chrome profile for auth.
Handles: single images, carousels, reels, videos, and captions.
"""

import os
import re
import time
import logging
import requests
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright

from grab.platform import find_chrome, find_chrome_profile

logger = logging.getLogger(__name__)


def download_instagram(url: str, output_dir: str) -> Dict:
    """
    Download an Instagram post using Playwright with the user's Chrome session.
    Supports single images, carousels, reels, and videos.
    """
    os.makedirs(output_dir, exist_ok=True)

    chrome_path = find_chrome()
    chrome_profile = find_chrome_profile()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            chrome_profile,
            executable_path=chrome_path,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            result = _extract_post(page, url, output_dir)
        except Exception as e:
            logger.error("Instagram extraction failed: %s", e)
            result = {"success": False, "error": str(e)}
        finally:
            context.close()

    return result


def _extract_post(page, url: str, output_dir: str) -> Dict:
    # Clean URL (remove query params like igsh)
    clean_url = url.split("?")[0]
    if not clean_url.endswith("/"):
        clean_url += "/"

    page.goto(clean_url, wait_until="domcontentloaded")
    time.sleep(3)

    # Check if we're redirected to login
    if "/accounts/login" in page.url:
        return {"success": False, "error": "Not logged in — open Chrome and log in to Instagram first"}

    # Dismiss cookie/notification popups
    _dismiss_popups(page)

    # Extract uploader first, then caption (caption needs uploader to strip prefix)
    uploader = _extract_uploader(page)
    caption = _extract_caption(page, uploader)

    # Detect content type and extract media
    media_files = []

    # Check for carousel (next button exists)
    is_carousel = page.locator('button[aria-label="Next"]').count() > 0

    # Check for video (search broadly)
    video_els = page.locator("video")
    is_video = video_els.count() > 0

    if is_carousel:
        media_files = _download_carousel(page, output_dir, uploader)
    elif is_video:
        media_files = _download_video(page, output_dir, uploader)
    else:
        media_files = _download_single_image(page, output_dir, uploader)

    return {
        "success": len(media_files) > 0,
        "title": _safe_name(uploader or "instagram_post"),
        "caption": caption,
        "media_files": media_files,
        "media_count": len(media_files),
        "info": {
            "uploader": uploader,
            "url": url,
            "is_carousel": is_carousel,
            "is_video": is_video,
        },
    }


def _dismiss_popups(page):
    """Dismiss common Instagram popups (login, cookies, notifications)."""
    selectors = [
        'button:has-text("Not Now")',
        'button:has-text("Decline")',
        'button:has-text("Allow essential")',
        'button:has-text("Accept")',
        '[role="dialog"] button[aria-label="Close"]',
        'svg[aria-label="Close"]',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click()
                time.sleep(0.5)
        except Exception:
            pass

    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
    except Exception:
        pass


def _extract_caption(page, uploader: str = "") -> str:
    """Extract post caption text."""
    try:
        spans = page.locator('span[dir="auto"]')
        best = ""
        for i in range(min(spans.count(), 20)):
            try:
                text = spans.nth(i).inner_text(timeout=2000)
                if text and len(text) > len(best):
                    best = text
            except Exception:
                continue

        if best:
            lines = best.strip().split("\n")
            start = 0
            for j, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped == uploader:
                    continue
                if re.match(r"^\d+[dhwm]$", stripped):
                    continue
                start = j
                break
            caption = "\n".join(lines[start:]).strip()
            if len(caption) > 10:
                return caption
    except Exception as e:
        logger.debug("Caption extraction failed: %s", e)
    return ""


def _extract_uploader(page) -> str:
    """Extract post author username from the page."""
    try:
        selectors = [
            'header a[role="link"]',
            'article header a',
            'a[href^="/"]:has(span)',
        ]
        for sel in selectors:
            els = page.locator(sel)
            for i in range(min(els.count(), 5)):
                href = els.nth(i).get_attribute("href", timeout=2000)
                if href and href.count("/") <= 2 and "explore" not in href and "accounts" not in href:
                    username = href.strip("/").split("/")[-1]
                    if username and len(username) > 1:
                        return username
    except Exception:
        pass

    try:
        title = page.title()
        if " on Instagram" in title:
            return title.split(" on Instagram")[0].strip().split("(")[-1].strip(")")
        if "(@" in title:
            return title.split("(@")[1].split(")")[0]
    except Exception:
        pass

    return ""


def _is_post_image(src: str) -> bool:
    """Check if URL is a real post image (not avatar/thumbnail)."""
    if not src:
        return False
    is_ig_cdn = "cdninstagram.com" in src or "fbcdn.net" in src
    is_avatar = "150x150" in src or "s150x150" in src
    is_post_media = "t51.82787" in src or "t51.29350" in src
    return is_ig_cdn and not is_avatar and is_post_media


def _get_image_urls(page) -> List[str]:
    """Get all visible post image URLs from the page."""
    urls = []
    imgs = page.locator("img[src]")
    count = imgs.count()
    for i in range(count):
        src = imgs.nth(i).get_attribute("src")
        if _is_post_image(src) and src not in urls:
            urls.append(src)
    return urls


def _download_single_image(page, output_dir: str, uploader: str) -> List[str]:
    """Download a single image post."""
    urls = _get_image_urls(page)
    if not urls:
        return []

    files = []
    for i, img_url in enumerate(urls[:1]):
        path = _save_media(img_url, output_dir, uploader, i + 1, "jpg")
        if path:
            files.append(path)
    return files


def _download_carousel(page, output_dir: str, uploader: str) -> List[str]:
    """Navigate through carousel and download all images/videos."""
    files = []
    seen_urls = set()
    slide_index = 0
    max_slides = 20

    while slide_index < max_slides:
        slide_index += 1
        time.sleep(1)

        video_el = page.locator("video")
        if video_el.count() > 0:
            vid_src = video_el.first.get_attribute("src")
            if vid_src and vid_src not in seen_urls:
                seen_urls.add(vid_src)
                path = _save_media(vid_src, output_dir, uploader, slide_index, "mp4")
                if path:
                    files.append(path)
        else:
            for img_url in _get_image_urls(page):
                if img_url not in seen_urls:
                    seen_urls.add(img_url)
                    path = _save_media(img_url, output_dir, uploader, len(files) + 1, "jpg")
                    if path:
                        files.append(path)

        next_btn = page.locator('button[aria-label="Next"]')
        if next_btn.count() > 0 and next_btn.is_visible():
            next_btn.click()
            time.sleep(1.5)
        else:
            break

    return files


def _download_video(page, output_dir: str, uploader: str) -> List[str]:
    """Download video/reel from post."""
    files = []
    video_el = page.locator("video").first

    if video_el.count() == 0:
        return files

    src = video_el.get_attribute("src")
    if src:
        path = _save_media(src, output_dir, uploader, 1, "mp4")
        if path:
            files.append(path)

    return files


def _save_media(url: str, output_dir: str, uploader: str,
                index: int, ext: str) -> Optional[str]:
    """Download a media URL to disk."""
    filename = f"{_safe_name(uploader)}_{index:03d}.{ext}"
    filepath = os.path.join(output_dir, filename)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.instagram.com/",
        }
        r = requests.get(url, headers=headers, timeout=30, stream=True)
        if r.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            logger.info("Saved: %s", filename)
            return filepath
        else:
            logger.warning("HTTP %d for %s", r.status_code, filename)
    except Exception as e:
        logger.error("Download failed for %s: %s", filename, e)

    return None


def _safe_name(name: str) -> str:
    clean = re.sub(r'[\\/*?:"<>|]', "_", name or "post")
    return re.sub(r'\s+', "_", clean).strip("_")[:60]
