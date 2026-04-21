# grab

Save content from YouTube and Instagram as structured, local files — organized as Obsidian-ready markdown with embedded media.

Instead of bookmarking links that break or relying on platform availability, `grab` downloads the actual content (transcripts, videos, images, captions) and turns it into markdown files you own. Each extraction is numbered, indexed, and uses Obsidian `![[embed]]` syntax so it works as a knowledge base out of the box.

## What it does

**YouTube**
- Downloads transcripts in any language and converts them to readable markdown
- Downloads video or audio files with quality control
- Saves thumbnails and metadata (channel, duration, URL)

**Instagram**
- Downloads full posts: single images, carousels (all slides), reels, and videos
- Extracts captions and uploader info
- Uses your Chrome session for auth — no API keys or tokens needed

**Every extraction** gets its own numbered folder with a markdown file, embedded media, and an entry in a master `index.md` that tracks everything.

## Works with

| Interface | How |
|-----------|-----|
| **Terminal** | `grab <url>` CLI command |
| **Claude Code** | `/grab <url>` skill |
| **Claude Desktop** | MCP tool — just ask Claude to grab a URL |

All three are configured automatically by the installer.

## Install

```bash
git clone https://github.com/caravana-assistant/grab.git
cd grab
./install.sh              # installs to ~/grab (default)
./install.sh ~/my-tools   # or pick your own directory
```

The installer handles everything:

- Creates an isolated `.venv/` with all dependencies
- Puts a `grab` wrapper at `~/.local/bin/grab`
- Installs Playwright Chromium (for Instagram)
- Sets up the Claude Code skill (`/grab`)
- Configures the Claude Desktop MCP server (`claude_desktop_config.json`)

### Requirements

- Python 3.10+
- ffmpeg — for video/audio downloads (`brew install ffmpeg` / `apt install ffmpeg`)
- Google Chrome — for Instagram (uses your logged-in session)

## Usage

### CLI

```bash
grab https://youtube.com/watch?v=xxx              # transcript → markdown
grab https://youtube.com/watch?v=xxx -m video      # download video
grab https://youtube.com/watch?v=xxx -m audio      # extract audio
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
| `--json` | off | Structured JSON output |

## Output structure

Each extraction gets a numbered folder. A master `index.md` links to all of them.

```
grab-output/
├── index.md                        ← master index with all extractions
├── 001_youtube_Video_Title/
│   ├── Video_Title.md              ← markdown with transcript + metadata
│   ├── Video_Title_thumb.jpg       ← thumbnail
│   └── Video_Title.pt-BR.json3    ← raw subtitle file
└── 002_instagram_username/
    ├── username.md                 ← markdown with caption + media embeds
    ├── username_001.jpg            ← carousel images
    ├── username_002.jpg
    └── ...
```

Markdown files use `![[filename]]` embeds — drop the output folder into an Obsidian vault and everything renders.

## Instagram auth

Instagram requires a logged-in Chrome session. The grabber launches Playwright with your Chrome profile, so just make sure you're logged in to Instagram in Chrome before running. No API keys, no tokens, no scraping services.

## Architecture

```
src/grab/
├── cli.py          # CLI entry point (grab command)
├── mcp_server.py   # MCP server for Claude Desktop
├── downloader.py   # yt-dlp wrapper for YouTube
├── instagram.py    # Playwright-based Instagram scraper
├── markdown.py     # Obsidian markdown generator
└── platform.py     # OS-aware path detection (ffmpeg, Chrome)
```

## License

MIT
