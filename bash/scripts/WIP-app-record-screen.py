#!/opt/homebrew/opt/python@3.11/libexec/bin/python3
import cv2
import numpy as np
import mss
import time
import os
import subprocess
from pynput import keyboard
from time import strftime, gmtime

ENABLE_GIF_EXPORT = True 

# --- Settings ---
fps = 8
is_recording = False
stop_recording = False
pressed_keys: set[str] = {'NOT_A_DIC(K)T'}

# --- Output Paths ---
ctime = strftime("%Y-%m-%d-%H%M%S", gmtime())
avi_path = os.path.expanduser(f"~/Desktop/sr-{ctime}.avi")
mp4_path = avi_path.replace(".avi", ".mp4")
gif_path = avi_path.replace(".avi", ".gif")

with mss.mss() as sct:
    monitor = sct.monitors[1]
    width = monitor["width"]
    height = monitor["height"]

# --- Utility Functions ---
def isMagicCombo():
    return 'alt' in pressed_keys and 'ctrl' in pressed_keys

def log(content: any, newlines=1) -> None:
    print(content)
    # with open(os.path.expanduser("~/og-logs.txt"), 'a') as f:
    #     f.write('\n' * newlines)
    #     f.write(str(content))


def keyKeyFromKey(key):
    k = str(key)
    if '.' in k:
        return k.split('.')[1].lower()
    return k

# --- Hotkey Handlers ---
def on_press(key):
    global is_recording, stop_recording, pressed_keys
    key = keyKeyFromKey(key)
    if key in pressed_keys:
        return
    pressed_keys.add(key)

    if not isMagicCombo():
        return

    if 'enter' in pressed_keys:
        if not is_recording:
            log("Started recording.")
            is_recording = True
    elif 'backspace' in pressed_keys:
        if is_recording:
            log("Stopping recording.")
            stop_recording = True

def on_release(key):
    global pressed_keys
    key = keyKeyFromKey(key)
    pressed_keys.remove(key)

# --- ffmpeg Helpers ---
def convert_avi_to_mp4(input_path, output_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vcodec", "libx264", "-crf", "28",
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(input_path)

def generate_gif_from_mp4(input_path, output_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "fps=8,scale=640:-1:flags=lanczos",
        "-loop", "0",
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# --- Start Keyboard Listener ---
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

# --- Initialize VideoWriter ---
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
out = cv2.VideoWriter(avi_path, fourcc, fps, (width, height))

if not out.isOpened():
    raise Exception("❌ VideoWriter failed to open.")

log("⌨️  Press Ctrl+Alt+Enter to start, Ctrl+Alt+Backspace to stop.")

# --- Recording Loop ---
with mss.mss() as sct:
    while not stop_recording:
        if is_recording:
            frame_start = time.time()
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            frame = cv2.resize(frame, (width, height))  # Ensure correct size
            out.write(frame)

            elapsed = time.time() - frame_start
            time.sleep(max(0, 1/fps - elapsed))
        else:
            time.sleep(0.1)

# --- Finalization ---
out.release()
listener.stop()
log("🧹 Cleaning up...")

convert_avi_to_mp4(avi_path, mp4_path)

if ENABLE_GIF_EXPORT:
    generate_gif_from_mp4(mp4_path, gif_path)

log("✅ Done.")
