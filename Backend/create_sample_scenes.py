from PIL import Image, ImageDraw
from pathlib import Path

output_dir = Path("generated/scenes")
output_dir.mkdir(parents=True, exist_ok=True)

scenes = [
    ("CYBERSECURITY", "Protect your digital world"),
    ("STRONG PASSWORDS", "Secure every account"),
    ("STAY ALERT", "Recognize suspicious links"),
]

for index, (heading, subtitle) in enumerate(scenes, start=1):
    image = Image.new("RGB", (1920, 1080), "#14243A")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (120, 260, 1800, 820),
        radius=40,
        fill="#203D5C",
        outline="#7DB5FF",
        width=4,
    )

    draw.text(
        (200, 410),
        heading,
        fill="white",
        font_size=100,
    )

    draw.text(
        (205, 570),
        subtitle,
        fill="#B9D7FF",
        font_size=52,
    )

    image.save(output_dir / f"scene_{index:02}.png")

print("Sample scene images created.")
