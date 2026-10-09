"""ContentForge AI Backend — Modular FastAPI Application.

Phase 1 Architectural Layout:
    React UI
      ↓
    FastAPI (main.py)
      ↓
    API Layer (api/routes, api/dependencies)
      ↓
    Ingestion & Extraction Modules (ingestion/, extraction/)
      ↓
    Core Domain Engines (services/, core/)
      ↓
    Local JSON & filesystem storage (storage/)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure Backend directory is in sys.path for 'app.*' imports
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Ensure project root 'bin' directory is in PATH for ffmpeg and ffprobe
_project_root = _backend_dir.parent
_bin_dir = _project_root / "bin"
if _bin_dir.is_dir() and str(_bin_dir) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"

from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .core.exceptions import AppException
from .core.logging import get_logger, setup_logging

# API Routers
from .api.routes.health import router as health_router
from .api.routes.projects import router as projects_router
from .api.routes.upload import router as upload_router
from .api.routes.sources import router as sources_router
from .api.routes.files import router as files_router
from .api.routes.analysis import router as analysis_router
from .api.routes.pipeline import router as pipeline_router
from .api.routes.transform import router as transform_router
from .api.routes.validation import router as consistency_validation_router
from .api.routes.uckr import router as uckr_full_router, uckr_router, validation_router, temp_router
from .api.routes.direct_text_routes import router as direct_text_router
from .api.routes.export_routes import router as export_routes_router
from .api.routes.doclink import router as doclink_full_router, doclink_router
from .api.routes.graph import router as neo4j_health_router, graph_router
from .api.routes.embeddings import router as embeddings_router
from .api.routes.rag import router as rag_router
from .api.routes.optimization import router as optimization_router
from .api.routes.models_route import router as models_router
from .api.routes.distillation import router as distillation_router
from .api.routes.active_params import router as active_params_router
from .api.routes.transformation import router as transformation_engine_router


# Initialize centralized logging
setup_logging()
log = get_logger("main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and graceful shutdown lifecycle."""
    log.info("Starting %s in %s mode (port %d)", settings.app_name, settings.environment, settings.port)
    # Background model cache initialization (bge-small-en-v1.5)
    try:
        import asyncio
        from .embeddings.embedder import get_embedder
        asyncio.create_task(asyncio.to_thread(get_embedder))
    except Exception as exc:
        log.warning("Embedding model pre-fetch deferred: %s", exc)
    yield
    log.info("%s backend shutdown complete.", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="ContentForge AI backend — Modular, multi-tenant AI transformation platform.",
    lifespan=lifespan,
)

# Global Exception Handlers
@app.exception_handler(AppException)
async def handle_app_exception(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": exc.message, "details": exc.details},
    )


# CORS Configuration
origins = [
    settings.frontend_origin,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if settings.extra_cors_origins.strip():
    origins += [o.strip() for o in settings.extra_cors_origins.split(",") if o.strip()]
origins = sorted(set(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router)
app.include_router(projects_router)
app.include_router(upload_router)
app.include_router(sources_router)
app.include_router(files_router)
app.include_router(analysis_router)
app.include_router(pipeline_router)
app.include_router(transform_router)
app.include_router(uckr_full_router)
app.include_router(uckr_router)
app.include_router(consistency_validation_router)
app.include_router(validation_router)
app.include_router(temp_router)
app.include_router(direct_text_router)
app.include_router(export_routes_router)
app.include_router(doclink_full_router)
app.include_router(doclink_router)
app.include_router(neo4j_health_router)
app.include_router(graph_router)
app.include_router(embeddings_router)
app.include_router(rag_router)
app.include_router(optimization_router)
app.include_router(models_router)
app.include_router(distillation_router)
app.include_router(active_params_router, prefix="/api/active-params", tags=["Active Parameters"])
app.include_router(transformation_engine_router)
from .api.routes.provenance import router as provenance_router
app.include_router(provenance_router)
from .api.routes.qubo import router as qubo_router
app.include_router(qubo_router)
from .api.routes.student import router as student_router
app.include_router(student_router)

# ── Media Generation Studio (Image + Video) ─────────────────────────────────
# Standalone packages at Backend/image and Backend/video. They use top-level
# package imports (from text..., from image..., from video...), so put the
# Backend root on sys.path and import by module path.
_backend_root = str(_backend_dir)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from image.routes import router as image_studio_router
from video.routes import router as video_studio_router

app.include_router(image_studio_router, prefix="/api/image-studio", tags=["Image Studio"])
app.include_router(video_studio_router, prefix="/api/media", tags=["Video Studio"])
app.include_router(video_studio_router)






