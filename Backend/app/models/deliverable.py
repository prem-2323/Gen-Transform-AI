"""Deliverables and Transformation Models (Phase 6)."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


AudienceType = Literal["executive", "technical", "general", "business", "analyst"]
ToneType = Literal["professional", "urgent", "informative", "persuasive", "authoritative", "conversational"]
DetailLevelType = Literal["concise", "medium", "comprehensive"]
ObjectiveType = Literal["awareness", "action", "education", "executive_briefing", "incident_response"]
DeliverableType = Literal[
    "linkedin",
    "x",
    "executive_summary",
    "advisory",
    "infographic",
    "presentation",
    "video_script",
]


class TransformationConfig(BaseModel):
    """User-selected configuration parameters for output transformation."""
    audience: str = "executive"
    tone: str = "professional"
    language: str = "English"
    detailLevel: str = "medium"
    objective: str = "awareness"


# Content Schemas for Deliverables

class LinkedInContent(BaseModel):
    title: str = ""
    body: str = ""
    hashtags: List[str] = Field(default_factory=list)
    usedFactIds: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class XPostItem(BaseModel):
    postNumber: int = 1
    text: str = ""
    usedFactIds: List[str] = Field(default_factory=list)


class XThreadContent(BaseModel):
    posts: List[XPostItem] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class ExecutiveSummaryContent(BaseModel):
    title: str = ""
    summary: str = ""
    keyFindings: List[str] = Field(default_factory=list)
    keyRisks: List[str] = Field(default_factory=list)
    recommendedActions: List[str] = Field(default_factory=list)
    usedFactIds: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class AdvisoryContent(BaseModel):
    title: str = ""
    severity: str = "UNKNOWN"  # CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
    summary: str = ""
    affectedEntities: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    usedFactIds: List[str] = Field(default_factory=list)


class InfographicSection(BaseModel):
    heading: str = ""
    content: str = ""


class InfographicKeyNumber(BaseModel):
    value: Any = ""
    label: str = ""


class InfographicContent(BaseModel):
    title: str = ""
    sections: List[InfographicSection] = Field(default_factory=list)
    keyNumbers: List[InfographicKeyNumber] = Field(default_factory=list)
    usedFactIds: List[str] = Field(default_factory=list)


class PresentationSlide(BaseModel):
    slideNumber: int = 1
    title: str = ""
    bullets: List[str] = Field(default_factory=list)
    usedFactIds: List[str] = Field(default_factory=list)


class PresentationContent(BaseModel):
    title: str = ""
    slides: List[PresentationSlide] = Field(default_factory=list)


class VideoScene(BaseModel):
    sceneNumber: int = 1
    durationSeconds: int = 10
    narration: str = ""
    visualDescription: str = ""
    usedFactIds: List[str] = Field(default_factory=list)


class VideoScriptContent(BaseModel):
    title: str = ""
    durationSeconds: int = 90
    scenes: List[VideoScene] = Field(default_factory=list)


class TransformationRequest(BaseModel):
    """Request payload for transforming canonical UCKR into deliverables."""
    sourceId: Optional[str] = None
    uckrVersion: Optional[int] = None
    outputTypes: List[DeliverableType] = Field(default_factory=lambda: ["linkedin"])
    configuration: TransformationConfig = Field(default_factory=TransformationConfig)


class DeliverableRecord(BaseModel):
    """Local repository record for a deliverable."""
    id: str = Field(alias="_id")
    userId: str
    projectId: str
    sourceId: str
    uckrId: str
    uckrVersion: int
    type: DeliverableType
    configuration: TransformationConfig
    content: Dict[str, Any]
    usedFactIds: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    status: Literal["completed", "failed", "generating", "validating"] = "completed"
    validation: Dict[str, Any] = Field(default_factory=lambda: {"valid": True})
    quality: Optional[Dict[str, Any]] = None
    qualityScore: Optional[float] = None
    groundingScore: Optional[float] = None
    qualityStatus: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    createdAt: str
    updatedAt: str

    model_config = {"populate_by_name": True, "extra": "allow"}


class DeliverablesModel(BaseModel):
    """Backward compatibility container for deliverables."""
    linkedin: Optional[Dict[str, Any]] = None
    twitter: Optional[Dict[str, Any]] = None
    advisory: Optional[Dict[str, Any]] = None
    infographic: Optional[Dict[str, Any]] = None
    executive_summary: Optional[Dict[str, Any]] = None
    presentation: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class TransformResponse(BaseModel):
    ok: bool = True
    projectId: str
    sourceId: str
    uckrVersion: int
    deliverables: List[Dict[str, Any]]
