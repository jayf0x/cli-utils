#!/usr/bin/env bash

MD="$HOME/Documents/Obsidian/<<       BREATHE       >>.md"
CACHE="$HOME/Library/Caches/custom-deletable"  # can reuse this folder for other projects.

HASH_FILE="$CACHE/hash"
TXT="$CACHE/content.txt"

CURRENT_HASH=$(shasum -a 256 "$MD" | awk '{print $1}')

IMG="$CACHE/background-$CURRENT_HASH.png"

if [[ -f "$HASH_FILE" ]]; then
    LAST_HASH=$(cat "$HASH_FILE")
else
    LAST_HASH=""
fi

echo $CURRENT_HASH
echo $LAST_HASH

if [[ "$CURRENT_HASH" != "$LAST_HASH" ]]; then
    echo "Generating new!"
    head -n 50 "$MD" > "$TXT"
    rm $CACHE/*.png &> /dev/null

    magick \
    -background black \
    -fill white \
    -font /System/Library/Fonts/Menlo.ttc \
    -pointsize 24 \
    -size 1000x1600 \
    caption:@"$TXT" \
    "$IMG"

    sleep 1

    osascript -e "tell application \"Finder\" to set desktop picture to POSIX file \"$IMG\""


    echo "$CURRENT_HASH" > "$HASH_FILE"
fi