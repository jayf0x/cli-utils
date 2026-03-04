import os
import sys
from langchain_community.llms import Ollama
from PIL import Image, ImageDraw, ImageFont
import subprocess
import textwrap
from datetime import datetime


# running on macOS only?

def read_file_content(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ['.txt', '.md']:
        print("File must be .txt or .md")
        sys.exit(1)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def summarize_with_ollama(content):
    model = Ollama(model="llama3")
    
    prompt = f"Summarize the following text into exactly 3-8 concise bullet-points. The idea is that your text output will be converted to a Desktop image, so make sure to fit the format/style (eg. no markdown):\n\n{content}"
    
    try:
        summary = model.invoke(prompt)
        return summary.strip()
    except Exception as e:
        print(f"Error with Ollama: {e}")
        sys.exit(1)

def create_text_imageV1(summary_text):
    # Image dimensions (adjust for your screen resolution)
    width, height = 1920, 1080  # Example: Full HD
    background_color = (255, 255, 255, 0)  # White
    text_color = (0, 0, 0)  # Black
    
    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)
    
    # Use a default font; adjust path if needed
    try:
        font = ImageFont.truetype("Arial.ttf", 50)  # macOS has Arial
    except IOError:
        font = ImageFont.load_default()
    
    # Wrap text to fit image
    wrapped_text = textwrap.fill(summary_text, width=60)  # Adjust wrap width as needed
    
    # Calculate text position
    text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) / 2
    y = (height - text_height) / 2
    
    draw.text((x, y), wrapped_text, font=font, fill=text_color)
    
    return image

def create_text_imageV2(summary_text):
    width, height = 1920, 1080
    background_color = (255, 255, 255, 0)
    text_color = (0, 0, 0)
    
    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype("Arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()
    
    # Split summary into lines (bullet-points)
    lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    
    # Optionally wrap each line if too long
    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(line, width=60))
    
    # Calculate total height
    sample_bbox = draw.textbbox((0, 0), 'A', font=font)
    line_height = sample_bbox[3] - sample_bbox[1] + 20  # 20px spacing between lines
    total_text_height = line_height * len(wrapped_lines)
    y = (height - total_text_height) / 2
    
    # Draw each line centered
    for line in wrapped_lines:
        text_width = draw.textlength(line, font=font)
        x = (width - text_width) / 2
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height
    
    return image

def create_text_imageV3(summary_text):
    MARGIN = 40  # pixels of margin around text
    LINE_SPACING = 30
    
    text_color = (255, 255, 255)
    background_color = (0, 0, 0)

    try:
        font = ImageFont.truetype("Arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()

    # Split summary into lines (bullet-points)
    lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

    # Optionally wrap each line if too long
    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(line, width=60))

    # Estimate max line width
    dummy_img = Image.new('RGB', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    max_line_width = max([dummy_draw.textlength(line, font=font) for line in wrapped_lines]) if wrapped_lines else 0

    # Estimate line height
    sample_bbox = dummy_draw.textbbox((0, 0), 'A', font=font)
    line_height = sample_bbox[3] - sample_bbox[1] + LINE_SPACING 

    # Calculate image size
    width = int(max_line_width + 2 * MARGIN)
    height = int(line_height * len(wrapped_lines) + 2 * MARGIN)

    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Draw each line centered
    y = MARGIN
    for line in wrapped_lines:
        text_width = draw.textlength(line, font=font)
        x = (width - text_width) / 2
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height

    return image


def create_text_image(summary_text):
    MARGIN = 40 
    LINE_SPACING = 30
    FONT_SIZE = 30
    MAX_WIDTH = 80

    text_color = (255, 255, 255)
    background_color = (0, 0, 0)

    try:
        font = ImageFont.truetype("Arial.ttf", FONT_SIZE)
    except IOError:
        font = ImageFont.load_default()

    # Split summary into lines (bullet-points)
    lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

    # Optionally wrap each line if too long
    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(line, width=MAX_WIDTH))

    # Estimate max line width
    dummy_img = Image.new('RGB', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    max_line_width = max([dummy_draw.textlength(line, font=font) for line in wrapped_lines]) if wrapped_lines else 0

    # Estimate line height
    sample_bbox = dummy_draw.textbbox((0, 0), 'A', font=font)
    line_height = sample_bbox[3] - sample_bbox[1] + LINE_SPACING

    # Calculate image size
    width = int(max_line_width + 2 * MARGIN)
    height = int(line_height * len(wrapped_lines) + 2 * MARGIN)

    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Draw each line left-aligned
    y = MARGIN
    for line in wrapped_lines:
        x = MARGIN
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height

    return image


def save_and_set_background(image):
    output_dir = os.path.expanduser("~/Pictures/backgrounds")
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"wallpaper_{timestamp}.png")
    
    image.save(output_path)
    print(f"Image saved to: {output_path}")
    
    # Set as desktop background using AppleScript
    applescript = f'tell application "System Events" to tell every desktop to set picture to "{output_path}"'
    subprocess.run(['osascript', '-e', applescript])
    print("Desktop background set.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_text_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    content = read_file_content(file_path)
    summary = summarize_with_ollama(content)
    print("Summary:\n" + summary)
    image = create_text_image(summary)
    save_and_set_background(image)