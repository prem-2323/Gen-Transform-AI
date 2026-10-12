==============================================================================
Gen-Transform-AI / DocLink Grounded RAG Platform
==============================================================================

QUICK START OPTIONS:
--------------------

[OPTION A] COMPLETE ASSET & MODEL DOWNLOADER (DOWNLOAD EVERYTHING FIRST):
  Double-click or run:
    .\download.bat
  (or via npm: npm run download)

  Downloads and caches all required components without launching servers:
    1. Python virtual environment (.venv) + installs all Backend/requirements.txt.
    2. Frontend node_modules via npm install.
    3. FFmpeg and FFprobe binaries automatically into bin\.
    4. HuggingFace 384d embedding model (BAAI/bge-small-en-v1.5).
    5. HuggingFace Diffusers image generation model (runwayml/stable-diffusion-v1-5).
    6. Ollama AI runtime + pulls qwen2.5:3b and gemma2:2b models.
    7. Stable Diffusion Forge repository + Realistic_Vision_V5.1.safetensors checkpoint.
    8. Applies NumPy 1.x compatibility fix for SD Forge.

[OPTION B] 1-CLICK INSTANT LAUNCH CONTROLLER:
  Double-click or run:
    .\start.bat

  What start.bat does automatically (No prompts / Instant Launch):
    1. Verifies Python 3.10+, Node.js 18+, Git, and FFmpeg prerequisites.
    2. Auto-provisions any missing packages (.venv, npm, FFmpeg, embeddings).
    3. Checks Ollama and pulls qwen2.5:3b and gemma2:2b if missing.
    4. Detects SD Forge and auto-downloads model checkpoint if missing.
    5. Auto-fixes Forge NumPy 2.x -> 1.26.4 + opencv 4.8.1.78 (:FIX_FORGE_NUMPY)
       and launches with --skip-python-version-check --api --listen --port 7860
       (fixes "numpy.dtype size changed" / "_ARRAY_API not found" crash).
    6. Automatically launches all 4 dedicated terminal windows:
         * Ollama AI Server Terminal (Port 11434)
         * SD Forge Image Studio Terminal (Port 7860)
         * FastAPI Backend API Server Terminal (Port 8000)
         * React / Vite Frontend Dev Server Terminal (Port 5173)
    7. Automatically opens http://localhost:5173 in your default browser (< 3s).

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
     - Automatically handled by download.bat / start.bat (places binaries in bin\).
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

   Model Checkpoint (.safetensors):
   - Place any SD 1.5 safetensors model into:
       models\Stable-diffusion\
     Example (Realistic Vision V5.1):
       curl.exe -L -C - -o "models\Stable-diffusion\Realistic_Vision_V5.1.safetensors" "https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/resolve/main/Realistic_Vision_V5.1.safetensors"

   REQUIREMENTS - Python + NumPy (critical, prevents crash):
   - Forge requires NumPy 1.x (pinned numpy==1.26.2 in requirements_versions.txt).
     NumPy 2.x crashes with:
       "ValueError: numpy.dtype size changed, may indicate binary incompatibility"
       "UserWarning: Failed to initialize NumPy: _ARRAY_API not found"
   - Fix command if needed:
       C:\GEN_AI_Environment\stable-diffusion-webui-forge\venv\Scripts\python.exe -m pip install "numpy==1.26.4" "opencv-contrib-python==4.8.1.78" --force-reinstall --no-cache-dir
     Verify:
       venv\Scripts\python.exe -c "import numpy, cv2; print(numpy.__version__, cv2.__version__); from skimage import exposure; print('skimage OK')"
       Expected: 1.26.4 4.8.1 / skimage OK

   Launch (API mode required for Image Studio on :7860):
     set COMMANDLINE_ARGS=--skip-python-version-check --api --listen --port 7860
     .\webui-user.bat

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
   python -m venv .venv
   .\.venv\Scripts\activate
   cd Backend
   pip install --upgrade pip
   pip install -r requirements.txt
   python download_model.py --all   # downloads embeddings + diffusers SD 1.5 model
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