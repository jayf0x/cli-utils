#!/bin/bash


# change to md file with TODO's
MD="$HOME/Documents/Obsidian/<<       BREATHE       >>.md"

# we don't need the output, macos makes copy of image anyways
cd /temp


if [[ $(find "$MD" -mmin -5) ]]; then
    markdown-to-png --input "$MD" --layout portrait --theme dark-purple --limit 1  

  osascript <<EOF
tell application "System Events"
set picture of every desktop to "$PNG"
end tell
EOF

fi