#!/usr/bin/env python3
import time, sys, os
from pathlib import Path
import subprocess

if len(sys.argv) < 2:
    print('[ERR] No folder path param was passed to choose images from')
    sys.exit(1)
    
folder_path = os.path.expanduser(sys.argv[1])

if not os.path.exists(folder_path):
        print(f"[ERR] Folder path not found: {folder_path}")
        sys.exit(1)


# Configuration
folder_path = Path(os.path.expanduser(folder_path))


# Get list of image files
files = sorted(folder_path.glob("*.jpg")) + \
        sorted(folder_path.glob("*.png")) + \
        sorted(folder_path.glob("*.jpeg"))


if not files:
    print("[ERR] No image files found.")
    exit(1)

# Calculate the index based on time / 600 seconds
# time_index = int(time.time() // 600)
time_index = int(time.time() // 6)
selected_index = time_index % len(files)
wallpaper = files[selected_index]

# Set wallpaper using AppleScript
subprocess.run([
    "osascript", "-e",
    f'tell application "System Events" to set picture of every desktop to POSIX file "{wallpaper}"'
])


# ~/Library/LaunchAgents/com.custom.background.plist


# com.custom.background