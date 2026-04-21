#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

# ── Config ────────────────────────────────────────────────────
NAS_IP="${NAS_IP:-100.66.29.49}"         # Tailscale IP (override with env var)
NAS_SHARE="${NAS_SHARE:-workspace}"       # Synology shared folder name
MOUNT_POINT="/workspace"
AGENT_LABEL="com.grab.workspace-mount"
AGENT_PLIST="$HOME/Library/LaunchAgents/${AGENT_LABEL}.plist"
MOUNT_SCRIPT="$HOME/.local/bin/mount-workspace"

echo ""
echo "  workspace setup"
echo "  ───────────────"
echo ""
echo "  NAS:   $NAS_IP"
echo "  Share: $NAS_SHARE"
echo "  Mount: $MOUNT_POINT"
echo ""

# ── Check Tailscale ───────────────────────────────────────────
if ping -c1 -W2 "$NAS_IP" &>/dev/null; then
    ok "NAS reachable at $NAS_IP"
else
    warn "NAS not reachable at $NAS_IP — make sure Tailscale is running"
fi

# ── Get NAS credentials ──────────────────────────────────────
echo ""
info "NAS credentials (Synology DSM user)"

# Check if already in Keychain
if security find-internet-password -s "$NAS_IP" -r "smb " &>/dev/null 2>&1; then
    NAS_USER=$(security find-internet-password -s "$NAS_IP" -r "smb " 2>&1 | grep "acct" | cut -d'"' -f4)
    ok "Credentials found in Keychain (user: $NAS_USER)"
    echo -n "  Use existing? [Y/n] "
    read -r use_existing
    if [[ "${use_existing,,}" == "n" ]]; then
        security delete-internet-password -s "$NAS_IP" -r "smb " &>/dev/null 2>&1 || true
    else
        NAS_PASS=$(security find-internet-password -s "$NAS_IP" -r "smb " -w 2>&1)
    fi
fi

if [ -z "${NAS_USER:-}" ] || [ -z "${NAS_PASS:-}" ]; then
    echo -n "  Username: "
    read -r NAS_USER
    echo -n "  Password: "
    read -rs NAS_PASS
    echo ""

    # Store in Keychain
    security add-internet-password \
        -a "$NAS_USER" \
        -s "$NAS_IP" \
        -w "$NAS_PASS" \
        -r "smb " \
        -l "NAS workspace ($NAS_IP)" \
        -T /usr/bin/security \
        -T /sbin/mount_smbfs \
        2>/dev/null || security delete-internet-password -s "$NAS_IP" -r "smb " &>/dev/null && \
        security add-internet-password \
            -a "$NAS_USER" \
            -s "$NAS_IP" \
            -w "$NAS_PASS" \
            -r "smb " \
            -l "NAS workspace ($NAS_IP)" \
            -T /usr/bin/security \
            -T /sbin/mount_smbfs

    ok "Credentials saved to Keychain"
fi

# ── Create mount point ────────────────────────────────────────
echo ""
if [ -d "$MOUNT_POINT" ]; then
    ok "Mount point exists: $MOUNT_POINT"
else
    info "Creating $MOUNT_POINT (requires sudo)"
    sudo mkdir -p "$MOUNT_POINT"
    sudo chown "$(whoami)" "$MOUNT_POINT"
    ok "Mount point created: $MOUNT_POINT"
fi

# ── Create mount script ──────────────────────────────────────
mkdir -p "$(dirname "$MOUNT_SCRIPT")"

cat > "$MOUNT_SCRIPT" << 'SCRIPT'
#!/usr/bin/env bash
# Mount NAS workspace — called by LaunchAgent or manually

NAS_IP="__NAS_IP__"
NAS_SHARE="__NAS_SHARE__"
MOUNT_POINT="__MOUNT_POINT__"

# Already mounted?
if mount | grep -q "$MOUNT_POINT"; then
    exit 0
fi

# Get credentials from Keychain
NAS_USER=$(security find-internet-password -s "$NAS_IP" -r "smb " 2>&1 | grep "acct" | cut -d'"' -f4)
NAS_PASS=$(security find-internet-password -s "$NAS_IP" -r "smb " -w 2>&1)

if [ -z "$NAS_USER" ] || [ -z "$NAS_PASS" ]; then
    echo "No credentials in Keychain for $NAS_IP"
    exit 1
fi

# Wait for network (Tailscale might take a moment after wake)
for i in $(seq 1 10); do
    ping -c1 -W2 "$NAS_IP" &>/dev/null && break
    sleep 2
done

# Mount
mount_smbfs "//${NAS_USER}:${NAS_PASS}@${NAS_IP}/${NAS_SHARE}" "$MOUNT_POINT" 2>/dev/null

if mount | grep -q "$MOUNT_POINT"; then
    echo "Mounted $MOUNT_POINT"
else
    echo "Failed to mount $MOUNT_POINT"
    exit 1
fi
SCRIPT

# Fill in config values
sed -i '' "s|__NAS_IP__|$NAS_IP|g" "$MOUNT_SCRIPT"
sed -i '' "s|__NAS_SHARE__|$NAS_SHARE|g" "$MOUNT_SCRIPT"
sed -i '' "s|__MOUNT_POINT__|$MOUNT_POINT|g" "$MOUNT_SCRIPT"
chmod +x "$MOUNT_SCRIPT"
ok "Mount script: $MOUNT_SCRIPT"

# ── Create LaunchAgent (auto-mount at login) ──────────────────
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$AGENT_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${MOUNT_SCRIPT}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>/tmp/workspace-mount.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/workspace-mount.log</string>
</dict>
</plist>
PLIST

launchctl unload "$AGENT_PLIST" 2>/dev/null || true
launchctl load "$AGENT_PLIST"
ok "LaunchAgent installed (auto-mounts at login + every 5min if disconnected)"

# ── Mount now ─────────────────────────────────────────────────
echo ""
info "Mounting workspace..."
"$MOUNT_SCRIPT"

if mount | grep -q "$MOUNT_POINT"; then
    ok "Mounted: $MOUNT_POINT"
else
    warn "Could not mount now — check NAS and Tailscale"
fi

# ── Create workspace structure ────────────────────────────────
echo ""
if [ -d "$MOUNT_POINT" ] && mount | grep -q "$MOUNT_POINT"; then
    mkdir -p "$MOUNT_POINT/vibe-coding"
    mkdir -p "$MOUNT_POINT/.claude-shared/memory"
    ok "Created: $MOUNT_POINT/vibe-coding/"
    ok "Created: $MOUNT_POINT/.claude-shared/memory/"
fi

# ── Claude Code memory symlink ────────────────────────────────
# Claude stores project memory at ~/.claude/projects/<encoded-path>/memory/
# For /workspace, the encoded path is "-workspace"
echo ""
CLAUDE_PROJECT_DIR="$HOME/.claude/projects/-workspace"
CLAUDE_MEMORY_DIR="$CLAUDE_PROJECT_DIR/memory"

mkdir -p "$CLAUDE_PROJECT_DIR"

if [ -L "$CLAUDE_MEMORY_DIR" ]; then
    ok "Claude memory symlink already exists"
elif [ -d "$CLAUDE_MEMORY_DIR" ]; then
    # Existing local memory — move to NAS and symlink
    info "Moving existing Claude memory to NAS..."
    cp -r "$CLAUDE_MEMORY_DIR"/* "$MOUNT_POINT/.claude-shared/memory/" 2>/dev/null || true
    rm -rf "$CLAUDE_MEMORY_DIR"
    ln -s "$MOUNT_POINT/.claude-shared/memory" "$CLAUDE_MEMORY_DIR"
    ok "Claude memory migrated to NAS and symlinked"
else
    ln -s "$MOUNT_POINT/.claude-shared/memory" "$CLAUDE_MEMORY_DIR"
    ok "Claude memory symlinked: $CLAUDE_MEMORY_DIR → NAS"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}Done!${NC}"
echo ""
echo "  Workspace:      $MOUNT_POINT"
echo "  Projects:       $MOUNT_POINT/vibe-coding/"
echo "  Claude memory:  shared via NAS"
echo "  Auto-mount:     at login + reconnects every 5min"
echo "  Mount manually: mount-workspace"
echo ""
echo "  Run this same script on your other Mac to sync both."
echo ""
