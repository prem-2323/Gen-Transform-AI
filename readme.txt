==============================================================================
Gen-Transform-AI / DocLink Grounded RAG Platform
==============================================================================

QUICK START (1-CLICK DIRECT AUTO-LAUNCHER):
--------------------------------------------
Double-click or run:
  .\start.bat

What start.bat does automatically (No prompts / Instant Launch):
  1. Checks Python 3.10+, Node.js 18+, Git, and FFmpeg prerequisites.
  2. Auto-detects or provisions FFmpeg (checks bin\ or system PATH).
  3. Detects SD Forge (in project directory or C:\GEN_AI_Environment, auto-clones if missing).
     Auto-fixes Forge NumPy 2.x -> 1.26.4 + opencv 4.8.1.78 (:FIX_FORGE_NUMPY)
     and launches with --skip-python-version-check --api --listen --port 7860
     (fixes "numpy.dtype size changed" / "_ARRAY_API not found" crash on Python 3.11).
  4. Detects Ollama (auto-downloads & installs silently if missing).
  5. Automatically launches all 4 dedicated terminal windows:
       * Ollama AI Server Terminal (Port 11434)
       * SD Forge Image Studio Terminal (Port 7860)
       * FastAPI Backend API Server Terminal (Port 8000)
       * React / Vite Frontend Dev Server Terminal (Port 5173)
  6. Automatically opens http://localhost:5173 in your default web browser.

------------------------------------------------------------------------------
MANUAL ENVIRONMENT SETUP (IF RUNNING MANUALLY):
------------------------------------------------------------------------------

1. FFmpeg & FFprobe Setup (Audio & Video Pipeline):
   -------------------------------------------------
   Linux (Download static AMD64 build into project bin/):
     cd ~/Gen-Transform-AI
     mkdir -p bin
     cd bin
     wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
     tar -xf ffmpeg-release-amd64-static.tar.xz

     find . -type f -name ffmpeg -executable -exec cp {} ./ffmpeg \;
     find . -type f -name ffprobe -executable -exec cp {} ./ffprobe \;

     ./ffmpeg -version
     cd ..

   Windows:
     - Automatically handled by start.bat, which places binaries into bin\.
     - Or manually install via winget:
         winget install Gyan.FFmpeg
       or place ffmpeg.exe and ffprobe.exe inside the project's bin\ folder.

2. Stable Diffusion Forge Setup (C:\GEN_AI_Environment):
   -----------------------------------------------------
   cd C:\
   mkdir GEN_AI_Environment
   cd GEN_AI_Environment
   git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
   cd stable-diffusion-webui-forge

   REQUIREMENTS - Python + NumPy (critical, prevents crash):
   - Forge f2.0.1 is tested on Python 3.10.6:
       https://www.python.org/downloads/release/python-3106/
     If you already have Python 3.11, launch with:
       set COMMANDLINE_ARGS=--skip-python-version-check --api --listen --port 7860
     (start.bat already adds --skip-python-version-check automatically).
   - Forge requires NumPy 1.x (pinned numpy==1.26.2 in
     requirements_versions.txt). NumPy 2.x crashes with:
       "ValueError: numpy.dtype size changed, may indicate binary incompatibility"
       "UserWarning: Failed to initialize NumPy: _ARRAY_API not found"
       at modules/processing.py -> skimage -> torch.
     start.bat auto-fixes this on every launch (:FIX_FORGE_NUMPY).
     Manual fix if needed:
       C:\GEN_AI_Environment\stable-diffusion-webui-forge\venv\Scripts\python.exe -m pip install "numpy==1.26.4" "opencv-contrib-python==4.8.1.78" --force-reinstall --no-cache-dir
     Verify:
       venv\Scripts\python.exe -c "import numpy, cv2; print(numpy.__version__, cv2.__version__); from skimage import exposure; print('skimage OK')"
       Expected: 1.26.4 4.8.1 / skimage OK
     NOTE: opencv-contrib-python 5.x requires numpy>=2, so keep
     opencv-contrib-python==4.8.1.78 with numpy 1.26.4.

   Launch (API mode required for Image Studio on :7860):
     set COMMANDLINE_ARGS=--skip-python-version-check --api --listen --port 7860
     .\webui-user.bat
   If Frontend shows "Forge Offline (Preview Mode)", Forge is not on
   http://127.0.0.1:7860 - restart it via start.bat.

3. Ollama AI Server & Models:
   --------------------------
   curl.exe -L -o OllamaSetup.exe "https://ollama.com/download/OllamaSetup.exe"
   .\OllamaSetup.exe /SILENT
   ollama serve
   ollama pull qwen2.5:3b
   ollama pull gemma2:2b
   ollama list

4. Backend (FastAPI):
   -------------------
   cd Backend
   pip install -r requirements.txt
   python download_model.py
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

5. Frontend (React + Vite):
   -------------------------
   cd Frontend
   npm install
   npm run dev

------------------------------------------------------------------------------
ACTIVE SERVICE URLS:
------------------------------------------------------------------------------
* Frontend Web UI:       http://localhost:5173
* Backend API:           http://localhost:8000
* Swagger API Docs:      http://localhost:8000/docs
* Backend Health Check:  http://localhost:8000/health
* Ollama Service:        http://localhost:11434
* SD Forge Image Gen:    http://localhost:7860
==============================================================================