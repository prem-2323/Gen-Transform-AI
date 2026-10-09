"""
Backend/main.py — Main entrypoint wrapper for ContentForge AI / Gen-Transform-AI.

Allows running directly from Backend/ directory:
    python main.py
    or
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import os
import sys
from pathlib import Path

# Ensure Backend and project root bin/ are in sys.path / PATH
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

_bin_dir = _backend_dir.parent / "bin"
if _bin_dir.is_dir() and str(_bin_dir) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"

from app.main import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

