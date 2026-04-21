---
name: grab
description: Download YouTube transcripts or Instagram posts (carousel, reels, videos) into Obsidian-ready markdown with embedded media. Use when the user shares a YouTube or Instagram URL and wants to grab content.
---

# /grab — YouTube & Instagram Content Grabber

Download YouTube transcripts or Instagram posts (carousel, reels, videos) into Obsidian-ready markdown with embedded media.

## Usage

```
/grab <url>
/grab <url> --mode video
/grab <url> --mode audio
/grab <url> -l en
/grab <url> -o ~/my-vault/content
```

## Behavior

When the user invokes `/grab` with a URL:

1. Detect the platform (YouTube or Instagram) from the URL
2. Run the grabber with the appropriate options
3. Report the results (folder path, media count, caption preview)

### Command

```bash
grab <url> [options] --json
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` / `-m` | `subtitle` | YouTube mode: `subtitle`, `video`, or `audio` |
| `--language` / `-l` | `pt` | Subtitle language code |
| `--output` / `-o` | `~/grab-output` | Output directory |
| `--quality` / `-q` | `1080p` | Video quality |
| `--audio-format` | `mp3` | Audio format |
| `--json` | off | Output structured JSON |

### Platform detection

- **YouTube**: `youtube.com`, `youtu.be` — downloads transcript by default, or video/audio with `--mode`
- **Instagram**: `instagram.com` — downloads all carousel images + caption + reels via Playwright (uses Chrome profile for auth)

### Output structure

Each extraction goes into a numbered folder:
```
output/
├── index.md
├── 001_youtube_Video_Title/
│   ├── Video_Title.md          (Obsidian markdown with ![[]] embeds)
│   ├── Video_Title_thumb.jpg   (YouTube thumbnail)
│   └── Video_Title.en.json3    (raw subtitle)
└── 002_instagram_username/
    ├── username.md             (Obsidian markdown with caption + ![[]] embeds)
    ├── username_001.jpg        (carousel images)
    └── ...
```

### After running

Report to the user:
- Extraction number and folder path
- For YouTube: title, channel, duration, language
- For Instagram: uploader, media count, first line of caption
- Link to the generated markdown file
