import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from .generator import generate_image_bytes


IMAGE_STORAGE = Path(os.getenv("IMAGE_STORAGE", "generated_images"))


def save_image(image_bytes: bytes, prefix: str = "image") -> str:
    """Validate, normalize, and persist generated image bytes as a PNG."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            normalized = image.convert("RGB")
    except Exception as error:
        raise ValueError("The image model returned invalid image data.") from error

    IMAGE_STORAGE.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.png"
    output_path = IMAGE_STORAGE / filename
    normalized.save(output_path, format="PNG", optimize=True)
    return filename


def generate_and_save_image(
    prompt: str,
    negative_prompt: str,
    width: int = 768,
    height: int = 768,
    steps: int = 10,
    mode: str = "fast",
    prefix: str = "image",
    allow_placeholder: bool = True,
) -> Tuple[str, float, str]:
    image_bytes, generation_time, device = generate_image_bytes(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        steps=steps,
        mode=mode,
        allow_placeholder=allow_placeholder,
    )
    filename = save_image(image_bytes, prefix)
    return filename, generation_time, device


def image_path(filename: str) -> Optional[Path]:
    """Resolve only files within the configured image storage directory."""
    candidate = (IMAGE_STORAGE / filename).resolve()
    storage_root = IMAGE_STORAGE.resolve()
    if candidate.parent != storage_root or candidate.suffix.lower() != ".png":
        return None
    return candidate if candidate.is_file() else None
