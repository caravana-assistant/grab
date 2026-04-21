#!/usr/bin/env python3
"""
grab — YouTube & Instagram content grabber.

Each extraction goes into its own numbered folder:
    output/001_youtube_Video_Title/
    output/002_instagram_username/

A master index.md tracks all extractions.

Usage:
    grab <url>                          # auto-detect platform + best action
    grab <url> --mode subtitle          # YouTube transcript -> markdown
    grab <url> --mode video             # YouTube video download
    grab <url> --mode audio             # YouTube audio download
    grab <url> -o ~/my-vault/Videos     # custom output directory
"""

import argparse
import json
import logging
import os
import sys
import tempfile

from grab.downloader import detect_platform, youtube_subtitle, youtube_media, youtube_info
from grab.instagram import download_instagram
from grab.markdown import (
    youtube_to_markdown, instagram_to_markdown,
    create_extraction_folder, update_index,
)
from grab.platform import default_output_dir, default_cookie_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("grab")


def run_youtube(url: str, mode: str, output_dir: str, language: str,
                cookie_file: str, quality: str, audio_format: str):

    if mode == "subtitle":
        logger.info("Downloading YouTube transcript...")
        result = youtube_subtitle(url, output_dir, language=language, cookie_file=cookie_file)
        if not result["success"]:
            logger.error("Failed: %s", result.get("error"))
            return result

        title = result.get("title", "Untitled")
        folder, num = create_extraction_folder(output_dir, "youtube", title)

        sub_file = result.get("subtitle_file")
        if sub_file and os.path.exists(sub_file):
            new_sub = os.path.join(folder, os.path.basename(sub_file))
            os.rename(sub_file, new_sub)
            result["subtitle_file"] = new_sub

        md_path = youtube_to_markdown(result, folder)
        result["markdown"] = md_path
        result["folder"] = folder

        md_filename = os.path.basename(md_path)
        folder_name = os.path.basename(folder)
        update_index(output_dir, num, "youtube", title, url, md_filename, folder_name)

        logger.info("Extraction #%03d saved: %s", num, folder)

    else:  # video or audio
        logger.info("Downloading YouTube %s...", mode)

        try:
            info = youtube_info(url)
            title = info.get("title", "Untitled")
        except Exception:
            title = "Untitled"

        folder, num = create_extraction_folder(output_dir, "youtube", title)

        result = youtube_media(url, folder, mode=mode, quality=quality,
                               audio_format=audio_format, cookie_file=cookie_file)
        if not result["success"]:
            logger.error("Failed: %s", result.get("error"))
            return result

        result["folder"] = folder
        update_index(output_dir, num, "youtube", title, url,
                     os.path.basename(result.get("media_path", "")),
                     os.path.basename(folder))

        logger.info("Extraction #%03d saved: %s", num, folder)

    return result


def run_instagram(url: str, output_dir: str):
    logger.info("Downloading Instagram post (Playwright + Chrome profile)...")

    tmp_dir = tempfile.mkdtemp(prefix="ig_", dir=output_dir)

    result = download_instagram(url, tmp_dir)

    if not result["success"]:
        logger.error("Failed: %s", result.get("error"))
        try:
            os.rmdir(tmp_dir)
        except Exception:
            pass
        return result

    uploader = result.get("info", {}).get("uploader", "instagram")
    folder, num = create_extraction_folder(output_dir, "instagram", uploader)

    for fname in os.listdir(tmp_dir):
        src = os.path.join(tmp_dir, fname)
        dst = os.path.join(folder, fname)
        os.rename(src, dst)

    result["media_files"] = [
        os.path.join(folder, os.path.basename(f))
        for f in result.get("media_files", [])
    ]

    try:
        os.rmdir(tmp_dir)
    except Exception:
        pass

    md_path = instagram_to_markdown(result, folder)
    result["markdown"] = md_path
    result["folder"] = folder

    title = f"{uploader} — post"
    md_filename = os.path.basename(md_path)
    folder_name = os.path.basename(folder)
    update_index(output_dir, num, "instagram", title, url, md_filename, folder_name)

    media_count = result.get("media_count", 0)
    logger.info("Extraction #%03d: %d media file(s) saved to %s", num, media_count, folder)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Grab YouTube transcripts & Instagram posts -> structured markdown",
    )
    parser.add_argument("url", help="YouTube or Instagram URL")
    parser.add_argument("--mode", "-m", choices=["subtitle", "video", "audio"],
                        default="subtitle",
                        help="Download mode for YouTube (default: subtitle). Ignored for Instagram.")
    parser.add_argument("--output", "-o", default=None,
                        help=f"Output directory (default: {default_output_dir()})")
    parser.add_argument("--language", "-l", default="pt",
                        help="Subtitle language (default: pt)")
    parser.add_argument("--cookies", "-c", default=None,
                        help="Cookie file path (Netscape format)")
    parser.add_argument("--quality", "-q", default="1080p",
                        help="Video quality (default: 1080p)")
    parser.add_argument("--audio-format", default="mp3",
                        help="Audio format (default: mp3)")
    parser.add_argument("--json", action="store_true",
                        help="Output result as JSON")

    args = parser.parse_args()

    output_dir = args.output or default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    cookie_file = args.cookies
    cookie_default = default_cookie_file()
    if not cookie_file and os.path.exists(cookie_default):
        cookie_file = cookie_default

    platform = detect_platform(args.url)

    if platform == "youtube":
        result = run_youtube(args.url, args.mode, output_dir, args.language,
                             cookie_file, args.quality, args.audio_format)
    elif platform == "instagram":
        result = run_instagram(args.url, output_dir)
    else:
        logger.info("Unknown platform, trying as YouTube...")
        result = run_youtube(args.url, args.mode, output_dir, args.language,
                             cookie_file, args.quality, args.audio_format)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result.get("success"):
        print(f"\nDone: {result.get('folder') or result.get('markdown')}")
    else:
        print(f"\nFailed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
