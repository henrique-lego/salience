#!/usr/bin/env bash
# Install the Salience weekly launchd plist
# Usage: ./scheduling/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.salience.weekly"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

# Unload existing if present
if launchctl list | grep -q "$PLIST_NAME" 2>/dev/null; then
    echo "Unloading existing $PLIST_NAME..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Substitute paths
UV_PATH="$(which uv)"
WORKING_DIR="$PROJECT_DIR"

echo "Configuring plist:"
echo "  uv path:     $UV_PATH"
echo "  project dir: $WORKING_DIR"

sed -e "s|/opt/homebrew/bin/uv|$UV_PATH|g" \
    -e "s|/Users/YOURUSER/source/workspaces/salience|$WORKING_DIR|g" \
    "$PLIST_SRC" > "$PLIST_DST"

# Load
launchctl load "$PLIST_DST"

echo "Installed and loaded $PLIST_NAME"
echo "Next run: Sunday at 09:07"
echo ""
echo "To uninstall:"
echo "  launchctl unload $PLIST_DST && rm $PLIST_DST"
