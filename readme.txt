==============================================================================
Gen-Transform-AI / DocLink Grounded RAG Platform
==============================================================================

QUICK START (1-CLICK DIRECT AUTO-LAUNCHER):
--------------------------------------------
Double-click or run:
  .\start.bat

What start.bat does automatically (No prompts / Instant Launch):
  1. Checks Python 3.10+, Node.js 18+, and Git prerequisites.
  2. Detects SD Forge (in project directory or C:\GEN_AI_Environment, auto-clones if missing).
  3. Detects Ollama (auto-downloads & installs silently if missing).
  4. Automatically launches all 4 dedicated terminal windows:
       * Ollama AI Server Terminal (Port 11434)
       * SD Forge Image Studio Terminal (Port 7860)
       * FastAPI Backend API Server Terminal (Port 8000)
       * React / Vite Frontend Dev Server Terminal (Port 5173)
  5. Automatically opens http://localhost:5173 in your default web browser.

------------------------------------------------------------------------------
MANUAL ENVIRONMENT SETUP (IF RUNNING MANUALLY):
------------------------------------------------------------------------------

1. Stable Diffusion Forge Setup (C:\GEN_AI_Environment):
   cd C:\
   mkdir GEN_AI_Environment
   cd GEN_AI_Environment
   git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
   cd stable-diffusion-webui-forge
   .\webui-user.bat


   cd ~/Gen-Transform-AI
   mkdir -p bin
cd bin
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz

find . -type f -name ffmpeg -executable -exec cp {} ./ffmpeg \;
find . -type f -name ffprobe -executable -exec cp {} ./ffprobe \;


./ffmpeg -version






2. Ollama AI Server & Models:
   curl.exe -L -o OllamaSetup.exe "https://ollama.com/download/OllamaSetup.exe"
   .\OllamaSetup.exe /SILENT
   ollama serve
   ollama pull qwen2.5:3b
   ollama pull gemma2:2b
   ollama list

3. Backend (FastAPI):
   cd Backend
   pip install -r requirements.txt
   python download_model.py
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

4. Frontend (React + Vite):
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