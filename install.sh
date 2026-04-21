#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

echo ""
echo "  grab installer"
echo "  ──────────────"
echo ""

# ── Check Python ──────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PY=$(python3 --version 2>&1)
    ok "Python: $PY"
else
    fail "Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

# ── Check ffmpeg ──────────────────────────────────────────────
if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
    warn "ffmpeg not found — video/audio downloads won't work"
    echo "       Install: brew install ffmpeg (macOS) / apt install ffmpeg (Linux)"
fi

# ── Check uv ──────────────────────────────────────────────────
if command -v uv &>/dev/null; then
    INSTALLER="uv pip install"
    ok "uv found"
else
    warn "uv not found, falling back to pip"
    INSTALLER="pip install"
fi

# ── Install package ───────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo "  Installing grab..."
$INSTALLER "$SCRIPT_DIR" 2>&1 | tail -1
echo ""

# ── Verify ────────────────────────────────────────────────────
if command -v grab &>/dev/null; then
    ok "grab command available"
else
    warn "grab not on PATH — you may need to restart your shell"
fi

# ── Install Playwright browsers ───────────────────────────────
echo ""
echo "  Installing Playwright Chromium (for Instagram)..."
python3 -m playwright install chromium 2>&1 | tail -3
ok "Playwright ready"

# ── Install Claude Code skill (optional) ──────────────────────
SKILL_SRC="$SCRIPT_DIR/skill/SKILL.md"
SKILL_DIRS=(
    "$HOME/vibe-coding/skills/grab"
    "$HOME/.claude/skills/grab"
)

echo ""
for SKILL_DIR in "${SKILL_DIRS[@]}"; do
    if [ -d "$(dirname "$SKILL_DIR")" ]; then
        mkdir -p "$SKILL_DIR"
        cp "$SKILL_SRC" "$SKILL_DIR/SKILL.md"
        ok "Skill installed: $SKILL_DIR"
        break
    fi
done

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}Done!${NC} Run: grab <youtube-or-instagram-url>"
echo "  Output goes to: ~/grab-output (or use -o to change)"
echo ""
