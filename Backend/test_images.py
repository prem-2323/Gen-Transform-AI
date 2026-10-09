from PIL import Image, ImageDraw
from pathlib import Path

folder = Path("generated/scenes")
folder.mkdir(parents=True, exist_ok=True)

scenes = [
    ("WELCOME", "AI Content Transformation"),
    ("STEP 1", "Analyze the document"),
    ("STEP 2", "Generate the final video"),
]

for i, (title, subtitle) in enumerate(scenes, start=1):
    image = Image.new("RGB", (1920, 1080), "#183153")
    draw = ImageDraw.Draw(image)

    draw.text((150, 400), title, fill="white")
    draw.text((150, 520), subtitle, fill="white")

    image.save(folder / f"scene_{i:02}.png")

print("SUCCESS: 3 sample images created")
