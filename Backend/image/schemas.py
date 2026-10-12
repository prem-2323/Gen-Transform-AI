from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, low resolution, distorted, deformed, bad anatomy, "
    "malformed hands, extra fingers, extra limbs, duplicate people, unnatural faces, "
    "distorted faces, cartoon, anime, illustration, watermark, logo, text, letters, "
    "empty room, empty office, vacant boardroom, conference table, empty chairs, blank screen, "
    "oversaturated, unrealistic, poor composition, cropped subjects"
)


class ImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT
    mode: str = Field("fast", description="Generation mode: fast (18 steps), balanced (22 steps), quality (28 steps)")
    width: int = Field(512, ge=256, le=1536)
    height: int = Field(512, ge=256, le=1536)
    steps: int = Field(20, ge=1, le=50)
    allow_placeholder: bool = Field(
        True,
        description="When True (default), return a labeled UI preview if Forge is offline. "
        "When False, return HTTP 503 instead so callers can show a real unavailable state.",
    )


class ImageResponse(BaseModel):
    status: str = "success"
    filename: str
    image_path: str
    image_url: Optional[str] = None
    generation_time: float = Field(..., description="Actual generation time in seconds")
    device: str = Field("cuda", description="Compute device used for inference (cuda/cpu)")
    steps: int = Field(20, description="Inference steps executed")
    width: int = Field(512, description="Image width in pixels")
    height: int = Field(512, description="Image height in pixels")
    synthetic: bool = Field(False, description="True when Stable Diffusion was offline and a preview placeholder was returned instead of AI-generated imagery")
    warning: Optional[str] = Field(None, description="Human-readable notice when synthetic is true")


class SceneImageRequest(BaseModel):
    script: Union[Dict[str, Any], str]
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT
    mode: str = Field("fast", description="Generation mode: fast, balanced, quality")
    width: int = Field(512, ge=256, le=1536)
    height: int = Field(512, ge=256, le=1536)
    steps: int = Field(20, ge=1, le=50)
    allow_placeholder: bool = Field(True, description="Allow labeled previews when Forge is offline.")


class SceneImageResponse(BaseModel):
    status: str = "success"
    images: List[ImageResponse]
    scenes: Optional[List[Dict[str, Any]]] = Field(
        None, description="Scene prompts used, in order (scene number + prompt)."
    )


class EnhancePromptRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000)
    style: Optional[str] = Field(None, description="Quick style label to apply as a visual constraint.")
    negative_prompt: Optional[str] = Field(None, description="User-supplied negative prompt to preserve.")
    aspect_ratio: Optional[str] = Field(None, description="Intended aspect ratio, e.g. 1:1, 16:9, 9:16, 4:3.")


class EnhancePromptResponse(BaseModel):
    status: str = "success"
    enhanced_prompt: str
    negative_prompt: str
    subject: str = ""
    agent: str = "image-prompt-enhancer"
    llm_used: bool = False
    warning: Optional[str] = None


class InfographicStatItem(BaseModel):
    value: str = "N/A"
    label: str = ""
    subtext: str = ""


class InfographicPointItem(BaseModel):
    title: str = ""
    description: str = ""


class InfographicRenderRequest(BaseModel):
    key_message: str = Field(..., min_length=1, max_length=500)
    key_statistics: List[InfographicStatItem] = Field(default_factory=list)
    supporting_points: List[InfographicPointItem] = Field(default_factory=list)
    call_to_action: str = Field("", max_length=500)
    layout: str = Field("Vertical", description="Vertical | Horizontal | Timeline | Process | Comparison")
    visual_style: str = Field("Corporate", description="Corporate | Minimal | Editorial | Technology")
    width: int = Field(1200, ge=400, le=2000)
    height: int = Field(800, ge=400, le=2000)
