"""Image Studio tests — Forge detection, generation, prompt agent, storyboard.

Uses mocked Forge API responses for determinism. Real inference is verified
separately (see Final Implementation Report); mocked success != real diffusion.
Run: .venv/Scripts/python.exe -m pytest Backend/tests/test_image_studio.py -v
"""
import base64
import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from image import prompt_engine as pe
from image.generator import ImageGenerationError, ImagePipelineSingleton, get_forge_base_url
from image.schemas import EnhancePromptRequest, ImageRequest, SceneImageRequest
from image.service import IMAGE_STORAGE, image_path, save_image


def _tiny_png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _forge_ok_response(png: bytes) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"images": [base64.b64encode(png).decode()]}
    return resp


def _fresh_pipeline() -> ImagePipelineSingleton:
    ImagePipelineSingleton._instance = None
    pipe = ImagePipelineSingleton.get_instance()
    # Fresh semaphore per test (previous failures must not leak permits).
    import threading
    pipe._forge_semaphore = threading.Semaphore(2)
    return pipe


# 1. Forge online / offline detection -------------------------------------
def test_status_online(monkeypatch):
    from image.routes import _check_forge_health
    ok = MagicMock(status_code=200)
    monkeypatch.setattr("requests.get", lambda *a, **k: ok)
    out = _check_forge_health()
    assert out["online"] is True and "online" in out["message"].lower()


def test_status_offline_connection_refused(monkeypatch):
    from image.routes import _check_forge_health
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("refused")
    monkeypatch.setattr("requests.get", boom)
    out = _check_forge_health()
    assert out["online"] is False and ("start.bat" in out["message"].lower() or "forge" in out["message"].lower())


def test_status_never_assumes_online_on_non_200(monkeypatch):
    from image.routes import _check_forge_health
    monkeypatch.setattr("requests.get", lambda *a, **k: MagicMock(status_code=500))
    assert _check_forge_health()["online"] is False


def test_forge_url_env_override(monkeypatch):
    monkeypatch.setenv("IMAGE_MODEL_URL", "http://host.docker.internal:7860/")
    assert get_forge_base_url() == "http://host.docker.internal:7860"


# 2. Connection failure / timeout handling --------------------------------
def test_connection_error_with_placeholder_false_raises():
    pipe = _fresh_pipeline()
    with patch.object(pipe, "_http_session") as sess:
        sess.post.side_effect = requests.exceptions.ConnectionError("down")
        with pytest.raises(ImageGenerationError, match="[Cc]ould not reach"):
            pipe.generate("a cat", allow_placeholder=False)


def test_read_timeout_message():
    pipe = _fresh_pipeline()
    with patch.object(pipe, "_http_session") as sess:
        sess.post.side_effect = requests.exceptions.ReadTimeout("slow")
        with pytest.raises(ImageGenerationError, match="timed out"):
            pipe.generate("a cat", allow_placeholder=False)


def test_http_error_message():
    pipe = _fresh_pipeline()
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("bad")
    resp.raise_for_status.side_effect.response = MagicMock(status_code=500)
    with patch.object(pipe, "_http_session") as sess:
        sess.post.return_value = resp
        with pytest.raises(ImageGenerationError, match="HTTP 500"):
            pipe.generate("a cat", allow_placeholder=False)


# 3. Valid / invalid generation parameters --------------------------------
def test_valid_params_accepted():
    req = ImageRequest(prompt="a lighthouse", width=1024, height=576, steps=18, mode="balanced")
    assert req.width == 1024 and req.steps == 18


@pytest.mark.parametrize("kwargs", [
    {"prompt": "x", "width": 100},      # below min
    {"prompt": "x", "width": 2000},     # above max
    {"prompt": "x", "steps": 0},        # below min
    {"prompt": "x", "steps": 99},       # above max
    {"prompt": ""},                     # empty
])
def test_invalid_params_rejected(kwargs):
    with pytest.raises(Exception):
        ImageRequest(**kwargs)


def test_invalid_mode_rejected_at_route():
    from fastapi import HTTPException
    from image.routes import _validate_mode
    with pytest.raises(HTTPException) as exc:
        _validate_mode("ultra")
    assert exc.value.status_code == 422


# 4/5. Prompt enhancement from long instructional text + subject preservation
LONG_INSTRUCTIONAL = (
    "Generate a LinkedIn post and a summary. Click Generate. "
    "Artificial intelligence is transforming the way information is processed "
    "and communicated across different domains."
)


def test_enhance_removes_procedural_keeps_subject(monkeypatch):
    # Force deterministic path (no LLM) for determinism.
    monkeypatch.setattr(pe, "_qwen_enhance", lambda prompt: None)
    out = pe.enhance_image_prompt(LONG_INSTRUCTIONAL, style="Editorial Magazine")
    assert "generate a linkedin" not in out["enhanced_prompt"].lower()
    assert "click" not in out["enhanced_prompt"].lower() or "generate" not in out["enhanced_prompt"].lower()
    assert "artificial intelligence" in out["enhanced_prompt"].lower()
    assert "no text" in out["enhanced_prompt"].lower()
    assert out["llm_used"] is False


def test_enhance_describes_scene_not_echo():
    out = pe.enhance_image_prompt(
        "Artificial intelligence is transforming the way information is processed and communicated.",
        style="Editorial Magazine",
    )
    # Must be a visual description, not the raw sentence alone.
    assert len(out["enhanced_prompt"]) > 80
    lowered = out["enhanced_prompt"].lower()
    assert any(k in lowered for k in ("illustration", "photography", "studio", "composition", "lighting", "palette", "image"))
    assert "no text" in lowered


# 6. Style injection + negative prompt handling ---------------------------
def test_style_constraint_applied(monkeypatch):
    monkeypatch.setattr(pe, "_qwen_enhance", lambda prompt: None)
    out = pe.enhance_image_prompt("a harbor at dawn", style="Cyberpunk Neon")
    assert "neon" in out["enhanced_prompt"].lower()


def test_negative_prompt_preserved(monkeypatch):
    monkeypatch.setattr(pe, "_qwen_enhance", lambda prompt: None)
    out = pe.enhance_image_prompt("a harbor", negative_prompt="blurry, watermark")
    assert out["negative_prompt"] == "blurry, watermark"


# 7. Correct forwarding of params to Forge --------------------------------
def test_forge_payload_forwarding():
    pipe = _fresh_pipeline()
    png = _tiny_png_bytes()
    # Pad to pass the 1024-byte sanity floor.
    png = png + b"\x00" * 2048
    with patch.object(pipe, "_http_session") as sess:
        sess.post.return_value = _forge_ok_response(png)
        pipe.generate("my prompt", negative_prompt="bad", width=1024, height=576, steps=18)
        _, kwargs = sess.post.call_args
        assert kwargs["json"]["prompt"] == "my prompt"
        assert kwargs["json"]["negative_prompt"] == "bad"
        assert kwargs["json"]["width"] == 1024
        assert kwargs["json"]["height"] == 576
        assert kwargs["json"]["steps"] == 18
        assert "/sdapi/v1/txt2img" in sess.post.call_args[0][0]


# 8. Successful decoding / delivery ---------------------------------------
def test_successful_decode_returns_bytes_and_not_synthetic():
    from image.generator import is_last_synthetic
    pipe = _fresh_pipeline()
    png = _tiny_png_bytes() + b"\x00" * 2048
    with patch.object(pipe, "_http_session") as sess:
        sess.post.return_value = _forge_ok_response(png)
        data, elapsed, device = pipe.generate("a cat")
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert is_last_synthetic() is False
        assert device in ("cpu", "cuda")
        assert elapsed >= 0


def test_save_and_resolve_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("image.service.IMAGE_STORAGE", tmp_path)
    from image import service as svc
    monkeypatch.setattr(svc, "IMAGE_STORAGE", tmp_path)
    fname = save_image(_tiny_png_bytes(), prefix="test")
    assert fname.endswith(".png")
    assert svc.image_path(fname) is not None


# 9. Failed generation handling -------------------------------------------
def test_placeholder_is_labeled_synthetic():
    from image.generator import is_last_synthetic
    pipe = _fresh_pipeline()
    with patch.object(pipe, "_http_session") as sess:
        sess.post.side_effect = requests.exceptions.ConnectionError("down")
        data, _, device = pipe.generate("a cat", allow_placeholder=True)
        assert is_last_synthetic() is True
        assert device == "cpu-preview"  # never claims GPU for previews
        assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_url_uses_api_prefix():
    from image.routes import _generate
    pipe = _fresh_pipeline()
    png = _tiny_png_bytes() + b"\x00" * 2048
    with patch("image.routes.generate_and_save_image", return_value=("f.png", 1.0, "cpu")):
        with patch("image.routes.is_last_synthetic", return_value=False):
            resp = _generate(ImageRequest(prompt="hi"))
            assert resp.image_url == "/api/image-studio/image/f.png"


# 11. Session history / downloads: path traversal guard --------------------
def test_image_path_blocks_traversal(tmp_path):
    from image import service as svc
    monkeypatch_storage = tmp_path
    import image.service as s2
    orig = s2.IMAGE_STORAGE
    try:
        s2.IMAGE_STORAGE = tmp_path
        assert s2.image_path("../secret.png") is None
        assert s2.image_path("evil.jpg") is None
        assert s2.image_path("nope.png") is None
    finally:
        s2.IMAGE_STORAGE = orig


# 12. Storyboard scene generation + ordering -------------------------------
def test_fallback_splits_long_script_into_ordered_scenes():
    script = (
        "Generate a LinkedIn post. "
        "Artificial intelligence is transforming information processing. "
        "Data centers glow at night. "
        "Teams collaborate on video screens."
    )
    scenes = pe._split_text_scenes(script)
    assert len(scenes) >= 3  # never collapses a multi-sentence script to one prompt
    assert [s["scene"] for s in scenes] == list(range(1, len(scenes) + 1))
    assert all(len(s["prompt"]) > 20 for s in scenes)


def test_storyboard_dict_ordering():
    script = {"storyboard": [{"scene": 2, "visuals": "night city"}, {"scene": 1, "visuals": "sunrise"}]}
    scenes = pe._fallback_scenes(script)
    assert len(scenes) == 2
    assert scenes[0]["prompt"] == "night city"  # preserves input order


def test_scene_response_includes_prompts():
    from image.routes import generate_scene_images
    from image.schemas import ImageResponse
    fake_scenes = [{"scene": 1, "prompt": "a cat"}, {"scene": 2, "prompt": "a dog"}]
    fake_images = [
        ImageResponse(status="success", filename="scene_01.png", image_path="generated_images/scene_01.png",
                      image_url="/api/image-studio/image/scene_01.png", generation_time=0.5, device="cpu",
                      steps=10, width=768, height=768, synthetic=True),
        ImageResponse(status="success", filename="scene_02.png", image_path="generated_images/scene_02.png",
                      image_url="/api/image-studio/image/scene_02.png", generation_time=0.5, device="cpu",
                      steps=10, width=768, height=768, synthetic=True),
    ]
    with patch("image.routes.generate_scene_prompts", return_value=fake_scenes):
        with patch("image.routes._generate", side_effect=fake_images) as gen:
            out = generate_scene_images(SceneImageRequest(script="anything"))
            assert out.scenes == fake_scenes
            assert len(out.images) == 2
            assert gen.call_count == 2
