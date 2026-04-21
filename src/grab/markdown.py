"""
Markdown generator — builds structured Obsidian-compatible .md files
from YouTube transcripts and Instagram posts.
Each extraction goes into its own numbered folder with an index.md master list.
"""

import os
import re
import logging
import yaml
import requests
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


INDEX_FILE = "index.md"


def get_next_number(output_dir: str) -> int:
    """Find the next extraction number by scanning existing folders."""
    if not os.path.isdir(output_dir):
        return 1
    max_num = 0
    for name in os.listdir(output_dir):
        match = re.match(r"^(\d{3})_", name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def create_extraction_folder(output_dir: str, platform: str, label: str) -> tuple[str, int]:
    """
    Create a numbered extraction folder.
    Returns (folder_path, number).
    """
    num = get_next_number(output_dir)
    folder_name = f"{num:03d}_{platform}_{_safe_filename(label)}"
    folder_path = os.path.join(output_dir, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path, num


def update_index(output_dir: str, num: int, platform: str,
                 title: str, url: str, md_filename: str, folder_name: str):
    """Append an entry to the master index.md."""
    index_path = os.path.join(output_dir, INDEX_FILE)

    # Create index header if it doesn't exist
    if not os.path.exists(index_path):
        header = "---\ntitle: Extractions Index\ndate_created: {}\n---\n\n# Extractions Index\n\n| # | Date | Platform | Title | Link |\n|---|------|----------|-------|------|\n".format(
            datetime.now().strftime("%Y-%m-%d")
        )
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(header)

    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = f"| {num:03d} | {date} | {platform} | [{title}]({folder_name}/{md_filename}) | [source]({url}) |\n"

    with open(index_path, "a", encoding="utf-8") as f:
        f.write(row)


def youtube_to_markdown(result: Dict, extraction_dir: str) -> str:
    """
    Build a markdown file from a YouTube subtitle download result.
    Files are saved inside the extraction folder.
    """
    info = result.get("info", {})
    title = result.get("title", "Untitled")
    text = result.get("text", "")

    frontmatter = {
        "title": title,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "source": info.get("uploader", "YouTube"),
        "platform": "youtube",
        "video_url": info.get("url", ""),
        "duration": info.get("duration"),
        "language": result.get("language", ""),
        "tags": ["youtube", "transcript"],
    }

    # Download thumbnail
    thumb_filename = None
    if info.get("thumbnail"):
        thumb_filename = _download_thumbnail(info["thumbnail"], extraction_dir, title)
        if thumb_filename:
            frontmatter["thumbnail"] = thumb_filename

    body = f"# {title}\n\n"

    # Embed thumbnail at the top
    if thumb_filename:
        body += f"![[{thumb_filename}]]\n\n"

    if info.get("url"):
        body += f"**Video:** [{info['url']}]({info['url']})\n\n"
    if info.get("uploader"):
        body += f"**Channel:** {info['uploader']}\n\n"
    if info.get("duration"):
        mins = info["duration"] // 60
        secs = info["duration"] % 60
        body += f"**Duration:** {mins}m {secs}s\n\n"

    body += "---\n\n## Transcript\n\n"
    body += _format_paragraphs(text)

    md_content = _build_md(frontmatter, body)

    filename = _safe_filename(title) + ".md"
    md_path = os.path.join(extraction_dir, filename)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return md_path


def instagram_to_markdown(result: Dict, extraction_dir: str) -> str:
    """
    Build a markdown file from an Instagram post download result.
    Media files are referenced relative to the extraction folder.
    """
    info = result.get("info", {})
    caption = result.get("caption", "")
    uploader = info.get("uploader", "instagram")
    media_files = result.get("media_files", [])

    frontmatter = {
        "title": f"{uploader} — post",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "source": uploader,
        "platform": "instagram",
        "post_url": info.get("url", ""),
        "media_count": len(media_files),
        "is_carousel": info.get("is_carousel", False),
        "is_video": info.get("is_video", False),
        "tags": ["instagram"],
    }

    if info.get("is_video"):
        frontmatter["tags"].append("reel" if "reel" in info.get("url", "") else "video")
    elif info.get("is_carousel"):
        frontmatter["tags"].append("carousel")
    else:
        frontmatter["tags"].append("photo")

    body = f"# {uploader}\n\n"

    if info.get("url"):
        body += f"**Post:** [{info['url']}]({info['url']})\n\n"

    body += "---\n\n"

    if caption:
        body += "## Caption\n\n"
        body += caption.strip() + "\n\n"

    if media_files:
        body += "---\n\n## Media\n\n"
        for i, fpath in enumerate(media_files, 1):
            fname = os.path.basename(fpath)
            ext = os.path.splitext(fname)[1].lower()
            if ext in (".jpg", ".jpeg", ".png", ".webp"):
                body += f"### Image {i}\n\n![[{fname}]]\n\n"
            elif ext in (".mp4", ".webm", ".mov"):
                body += f"### Video {i}\n\n![[{fname}]]\n\n"
            else:
                body += f"- [[{fname}]]\n\n"

    md_content = _build_md(frontmatter, body)

    filename = _safe_filename(uploader) + ".md"
    md_path = os.path.join(extraction_dir, filename)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return md_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_thumbnail(url: str, output_dir: str, title: str) -> str | None:
    """Download a thumbnail image and return the filename."""
    filename = _safe_filename(title) + "_thumb.jpg"
    filepath = os.path.join(output_dir, filename)
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(r.content)
            logger.info("Thumbnail saved: %s", filename)
            return filename
    except Exception as e:
        logger.debug("Thumbnail download failed: %s", e)
    return None


def _build_md(frontmatter: dict, body: str) -> str:
    fm = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{fm}---\n\n{body}\n"


def _format_paragraphs(text: str, max_len: int = 200) -> str:
    sentences = text.split(". ")
    paragraphs = []
    current = []
    length = 0

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if not s.endswith("."):
            s += "."
        if length + len(s) > max_len and current:
            paragraphs.append(" ".join(current))
            current = [s]
            length = len(s)
        else:
            current.append(s)
            length += len(s)

    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs) + "\n"


def _safe_filename(name: str, max_len: int = 60) -> str:
    clean = re.sub(r'[\\/*?:"<>|]', "_", name or "untitled")
    clean = re.sub(r'\s+', "_", clean).strip("_")
    return clean[:max_len]
