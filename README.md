# grab

YouTube & Instagram content grabber that outputs Obsidian-ready markdown with embedded media.

**YouTube** — transcripts, video, audio  
**Instagram** — carousels, reels, videos, captions (via Playwright + Chrome session)

## Install

```bash
git clone https://github.com/caravana-assistant/grab.git
cd grab
./install.sh              # installs to ~/grab (default)
./install.sh ~/my-tools   # or pick your own directory
```

One script sets up everything:

- `.venv/` with all dependencies
- `grab` CLI at `~/.local/bin/grab`
- Playwright Chromium for Instagram
- Claude Code skill (`/grab`)
- Claude Desktop MCP tool (auto-configures `claude_desktop_config.json`)

### Requirements

- Python 3.10+
- ffmpeg (for video/audio downloads)
- Google Chrome (for Instagram — uses your logged-in session)

## Usage

### CLI

```bash
grab https://youtube.com/watch?v=xxx              # transcript → markdown
grab https://youtube.com/watch?v=xxx -m video      # download video
grab https://youtube.com/watch?v=xxx -m audio      # download audio
grab https://youtube.com/watch?v=xxx -l en         # english subtitles
grab https://instagram.com/p/xxx                   # post, carousel, or reel
grab <url> -o ~/my-vault/content                   # custom output dir
```

### Claude Code

```
/grab https://youtube.com/watch?v=xxx
/grab https://instagram.com/reel/xxx
```

### Claude Desktop

After install, restart Claude Desktop. The `grab` tool appears automatically — just ask Claude to grab a URL.

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` / `-m` | `subtitle` | YouTube: `subtitle`, `video`, or `audio` |
| `--language` / `-l` | `pt` | Subtitle language code |
| `--output` / `-o` | `~/grab-output` | Output directory |
| `--quality` / `-q` | `1080p` | Video quality |
| `--audio-format` | `mp3` | Audio format |
| `--json` | off | Output structured JSON |

## Output

Each extraction goes into a numbered folder with Obsidian-compatible markdown:

```
grab-output/
├── index.md
├── 001_youtube_Video_Title/
│   ├── Video_Title.md
│   ├── Video_Title_thumb.jpg
│   └── Video_Title.pt-BR.json3
└── 002_instagram_username/
    ├── username.md
    ├── username_001.jpg
    ├── username_002.jpg
    └── ...
```

Markdown files use `![[filename]]` embeds for images, videos, and thumbnails — ready to drop into an Obsidian vault.

## Instagram auth

Instagram requires a logged-in Chrome session. The grabber launches Playwright with your Chrome profile — just make sure you're logged in to Instagram in Chrome before running.

## Architecture

```
src/grab/
├── cli.py          # CLI entry point
├── mcp_server.py   # MCP server for Claude Desktop
├── downloader.py   # yt-dlp wrapper (YouTube + fallback Instagram)
├── instagram.py    # Playwright-based Instagram scraper
├── markdown.py     # Obsidian markdown generator
└── platform.py     # OS-aware path detection (ffmpeg, Chrome)
```
