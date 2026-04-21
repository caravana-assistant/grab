"""
MCP server for grab — exposes YouTube & Instagram grabber as a tool
for Claude Desktop and other MCP clients.
"""

import json
import logging
import os
import tempfile

from mcp.server.fastmcp import FastMCP

from grab.downloader import detect_platform, youtube_subtitle, youtube_info
from grab.instagram import download_instagram
from grab.markdown import (
    youtube_to_markdown, instagram_to_markdown,
    create_extraction_folder, update_index,
)
from grab.platform import default_output_dir, default_cookie_file

logger = logging.getLogger("grab.mcp")

mcp = FastMCP(
    "grab",
    description="Download YouTube transcripts and Instagram posts into Obsidian-ready markdown",
)


@mcp.tool()
def grab(
    url: str,
    mode: str = "subtitle",
    language: str = "pt",
    output_dir: str = "",
    quality: str = "1080p",
    audio_format: str = "mp3",
) -> str:
    """Download a YouTube transcript/video/audio or Instagram post into structured markdown.

    Args:
        url: YouTube or Instagram URL
        mode: For YouTube — "subtitle" (default), "video", or "audio". Ignored for Instagram.
        language: Subtitle language code (default: "pt")
        output_dir: Output directory (default: ~/grab-output)
        quality: Video quality (default: "1080p")
        audio_format: Audio format (default: "mp3")
    """
    out = output_dir or default_output_dir()
    os.makedirs(out, exist_ok=True)

    cookie_file = None
    cookie_default = default_cookie_file()
    if os.path.exists(cookie_default):
        cookie_file = cookie_default

    platform = detect_platform(url)

    if platform == "instagram":
        result = _run_instagram(url, out)
    else:
        result = _run_youtube(url, mode, out, language, cookie_file, quality, audio_format)

    return json.dumps(result, ensure_ascii=False, indent=2)


def _run_youtube(url, mode, output_dir, language, cookie_file, quality, audio_format):
    from grab.downloader import youtube_media

    if mode == "subtitle":
        result = youtube_subtitle(url, output_dir, language=language, cookie_file=cookie_file)
        if not result["success"]:
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

    else:
        try:
            info = youtube_info(url)
            title = info.get("title", "Untitled")
        except Exception:
            title = "Untitled"

        folder, num = create_extraction_folder(output_dir, "youtube", title)

        result = youtube_media(url, folder, mode=mode, quality=quality,
                               audio_format=audio_format, cookie_file=cookie_file)
        if not result["success"]:
            return result

        result["folder"] = folder
        update_index(output_dir, num, "youtube", title, url,
                     os.path.basename(result.get("media_path", "")),
                     os.path.basename(folder))

    return result


def _run_instagram(url, output_dir):
    tmp_dir = tempfile.mkdtemp(prefix="ig_", dir=output_dir)

    result = download_instagram(url, tmp_dir)

    if not result["success"]:
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

    return result


def main():
    mcp.run()


if __name__ == "__main__":
    main()
