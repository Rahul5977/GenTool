#!/bin/bash
# Install Noto Sans Devanagari for Hindi text overlays
set -e

echo "Installing Noto Sans Devanagari font..."

# Try apt-get first (Ubuntu/Debian)
if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq fonts-noto 2>/dev/null || true
fi

# Verify font is available
if fc-match "NotoSansDevanagari" 2>/dev/null | grep -qi "noto"; then
    echo "✓ Noto Sans Devanagari installed successfully"
    fc-match --format="%{file}\n" "NotoSansDevanagari"
else
    echo "⚠ Font not installed via apt — downloading manually..."
    FONT_DIR="/usr/local/share/fonts"
    sudo mkdir -p "$FONT_DIR"
    # Note: in production, download the font from Google Fonts
    echo "Please download NotoSansDevanagari-Regular.ttf from Google Fonts"
    echo "and place it in $FONT_DIR"
fi
