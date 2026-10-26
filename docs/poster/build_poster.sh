#!/usr/bin/env bash
# Render docs/poster/poster.html to an A1 PDF (print) and a PNG preview, using Windows Chrome headless.
# Windows Chrome cannot read the WSL filesystem by file:// path, so the poster folder is copied to Windows temp first.
# Usage: docs/poster/build_poster.sh            -> docs/poster/Group13_CodeFair_Poster.pdf / .png
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CHROME="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
WIN_USER="${WIN_USER:-bigyan}"
TMP_LX="/mnt/c/Users/$WIN_USER/AppData/Local/Temp/g13_poster"
TMP_WIN="C:\\Users\\$WIN_USER\\AppData\\Local\\Temp\\g13_poster"
URL="file:///C:/Users/$WIN_USER/AppData/Local/Temp/g13_poster/poster.html"

rm -rf "$TMP_LX" && mkdir -p "$TMP_LX"
cp -r "$HERE/poster.html" "$HERE/assets" "$TMP_LX/"

# PDF: exact A1 page from the CSS @page rule; the time budget lets Google Fonts load before printing.
timeout 120 "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=15000 \
  --print-to-pdf="$TMP_WIN\\poster.pdf" "$URL" >/dev/null 2>&1
# PNG preview: 594 x 841 mm at 96 px/in = 2245 x 3179 css px, rendered at 2x (4490 x 6358).
timeout 120 "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=2245,3179 --virtual-time-budget=15000 --screenshot="$TMP_WIN\\poster.png" "$URL" >/dev/null 2>&1

cp "$TMP_LX/poster.pdf" "$HERE/Group13_CodeFair_Poster.pdf"
cp "$TMP_LX/poster.png" "$HERE/Group13_CodeFair_Poster.png"
pdfinfo "$HERE/Group13_CodeFair_Poster.pdf" | grep -E "Pages|Page size"
# Layout check: natural content height must be <= 841 mm or the bottom of the poster is clipped.
timeout 120 "$CHROME" --headless=new --disable-gpu --window-size=2245,3179 --virtual-time-budget=15000 --dump-dom "$URL" 2>/dev/null \
  | grep -o 'data-measure="[^"]*"' | sed 's/&quot;/"/g'
