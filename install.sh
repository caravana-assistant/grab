#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"

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
HAS_UV=false
if command -v uv &>/dev/null; then
    HAS_UV=true
    ok "uv found"
else
    warn "uv not found, using python3 -m venv + pip"
fi

# ── Create venv ───────────────────────────────────────────────
echo ""
echo "  Creating virtual environment..."

if $HAS_UV; then
    uv venv "$VENV_DIR" 2>&1 | tail -1
else
    python3 -m venv "$VENV_DIR"
fi
ok "venv: $VENV_DIR"

# ── Install package into venv ─────────────────────────────────
echo ""
echo "  Installing grab into venv..."

if $HAS_UV; then
    uv pip install --python "$VENV_DIR/bin/python" "$SCRIPT_DIR" 2>&1 | tail -1
else
    "$VENV_DIR/bin/pip" install "$SCRIPT_DIR" 2>&1 | tail -1
fi
ok "Package installed"

# ── Install Playwright browsers ───────────────────────────────
echo ""
echo "  Installing Playwright Chromium (for Instagram)..."
"$VENV_DIR/bin/python" -m playwright install chromium 2>&1 | tail -3
ok "Playwright ready"

# ── Create wrapper script on PATH ─────────────────────────────
echo ""
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/grab" << WRAPPER
#!/usr/bin/env bash
exec "$VENV_DIR/bin/grab" "\$@"
WRAPPER
chmod +x "$BIN_DIR/grab"
ok "Wrapper: $BIN_DIR/grab"

# Check if ~/.local/bin is on PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not on your PATH"
    echo "       Add to your shell profile:"
    echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── Verify ────────────────────────────────────────────────────
if "$VENV_DIR/bin/grab" --help &>/dev/null; then
    ok "grab command works"
else
    warn "grab installed but could not verify — check manually"
fi

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

# ── Update SKILL.md command path ──────────────────────────────
INSTALLED_SKILL=""
for SKILL_DIR in "${SKILL_DIRS[@]}"; do
    if [ -f "$SKILL_DIR/SKILL.md" ]; then
        INSTALLED_SKILL="$SKILL_DIR/SKILL.md"
        break
    fi
done

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}Done!${NC} Run: grab <youtube-or-instagram-url>"
echo "  Output goes to: ~/grab-output (or use -o to change)"
echo "  Venv: $VENV_DIR"
echo ""
