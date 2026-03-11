import os
import sys
import subprocess
from send2trash import send2trash
from pathlib import Path


def compress_video(input_path):
    if not input_path:
        return
    # Validate file
    # if not input_path.endswith(".mov") or not os.path.basename(input_path).startswith("Screen Recording"):
    #     print(f"Skipped: {input_path} is not a valid screen recording.")
    #     return

    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    output_path = os.path.splitext(input_path)[0] + ".mp4"

    # ffmpeg command without audio
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vcodec", "libx264",
        "-crf", "28",
        "-preset", "slow",
        "-an",  # No audio
        output_path
    ]

    print(f"Compressing: {input_path} -> {output_path}")
    result = subprocess.run(cmd, capture_output=True)

    if result.returncode == 0:
        if os.path.exists(input_path):
            send2trash(input_path)
            print(f"Success: Compressed and moved original to Trash: {input_path}")
        else:
            # Clean up: don't keep the .mp4 if original vanished
            os.remove(output_path)
            print(f"Original {input_path} missing after compression. Removed output.")
    else:
        print(f"Error compressing {input_path}")
        print(result.stderr.decode())

if __name__ == "__main__":
    paths = sys.argv[1:]
    if sys.argv[1] == '-y':
        paths = Path(os.path.expanduser('~/Desktop')).glob("*.mov")

    for path in paths:
        compress_video(path)
