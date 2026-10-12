# Gen-Transform-AI / DocLink Grounded RAG Platform

> **Production-grade AI transformation platform converting complex unstructured enterprise documents into grounded executive advisories, verified reports, AI video scripts, voiceover narrations, and photorealistic visual scenes.**

---

## ⚡ Quick Start (1-Click Automated Launchers)

### 🚀 Option 1: 1-Click Master Launch Controller (`start.bat`)
Double-click or run from PowerShell / Command Prompt:
```bat
.\start.bat
```
**What `start.bat` does automatically:**
1. **Pre-flight Check**: Validates Git, Python 3.10+, Node.js 18+, and FFmpeg.
2. **Auto-Provisions Missing Dependencies**:
   - Creates Python `.venv` and installs all packages from `Backend/requirements.txt`.
   - Runs `npm install` inside `Frontend/` if `node_modules` is missing.
   - Auto-downloads FFmpeg and FFprobe binaries into `bin\` if missing.
   - Auto-caches HuggingFace embedding model (`BAAI/bge-small-en-v1.5`).
   - Auto-installs Ollama and pulls `qwen2.5:3b` and `gemma2:2b` if missing.
   - Auto-clones SD Forge and downloads photorealistic model checkpoint (`Realistic_Vision_V5.1.safetensors`) if missing.
   - Auto-applies Forge NumPy 1.x compatibility patch (`numpy==1.26.4`).
3. **Launches All 4 Terminals Concurrently**:
   - Terminal 1: **Ollama AI Server** (Port `11434`)
   - Terminal 2: **Stable Diffusion Forge WebUI / Image API** (Port `7860`)
   - Terminal 3: **FastAPI Backend API Server** (Port `8000`)
   - Terminal 4: **React / Vite Frontend Dev Server** (Port `5173`)
4. **Opens the Web Application** in your default browser at `http://localhost:5173` within 3 seconds.

---

### 📦 Option 2: Pre-Download All Models & Assets (`download.bat`)
If you want to download and cache all weights, checkpoints, binaries, and dependencies **before running servers**, run:
```bat
.\download.bat
```
*(Or via npm: `npm run download` / `npm run setup`)*

**What `download.bat` downloads and configures:**
- ✅ **Python Virtual Environment (`.venv`)**: Upgrades pip and installs all Backend libraries.
- ✅ **Frontend Packages**: Installs `node_modules` via `npm install`.
- ✅ **FFmpeg & FFprobe**: Downloads Windows GPL build zip from GitHub releases and unpacks `ffmpeg.exe` and `ffprobe.exe` into `bin\`.
- ✅ **Embedding Model**: Downloads and caches `BAAI/bge-small-en-v1.5` (384d) for offline hybrid vector search.
- ✅ **Diffusers Image Generation Model**: Downloads and caches `runwayml/stable-diffusion-v1-5` (~4 GB) via HuggingFace Diffusers pipeline for text-to-image synthesis.
- ✅ **Ollama Runtime & Models**:
  - Installs Ollama silently if not present.
  - Pulls `qwen2.5:3b` (Incident analysis, grounded Q&A, and video script generation).
  - Pulls `gemma2:2b` (Scene visual descriptions and visual validation).
- ✅ **Stable Diffusion Forge & Checkpoint**:
  - Clones `stable-diffusion-webui-forge` into `C:\GEN_AI_Environment`.
  - Downloads `Realistic_Vision_V5.1.safetensors` (~4.2 GB) with resume support into `models/Stable-diffusion`.
  - Fixes Forge NumPy 1.x / skimage compatibility.

---

## 🌐 Active Service Ports & Endpoints

| Service | Address | Description |
| :--- | :--- | :--- |
| **Frontend Web UI** | [http://localhost:5173](http://localhost:5173) | Modern React 19 + Vite + Tailwind interface |
| **Backend API** | [http://localhost:8000](http://localhost:8000) | FastAPI REST service |
| **Swagger API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive OpenAPI / Swagger UI |
| **Backend Health** | [http://localhost:8000/health](http://localhost:8000/health) | System health & service connectivity status |
| **Ollama AI Server** | [http://localhost:11434](http://localhost:11434) | Local LLM inference engine (`qwen2.5:3b`, `gemma2:2b`) |
| **SD Forge Image API** | [http://localhost:7860](http://localhost:7860) | Stable Diffusion Forge txt2img generation server |

---

## 🛠️ Manual Installation & Setup Guide

If you prefer to configure components step-by-step manually:

### 1. System Prerequisites
- **Git**: [https://git-scm.com/](https://git-scm.com/)
- **Python 3.10 or 3.11**: [https://www.python.org/](https://www.python.org/)
- **Node.js 18+ & NPM**: [https://nodejs.org/](https://nodejs.org/)

### 2. FFmpeg & FFprobe Setup
#### Windows:
Place `ffmpeg.exe` and `ffprobe.exe` inside the project `bin\` directory, or install via winget:
```powershell
winget install Gyan.FFmpeg
```
#### Linux:
```bash
mkdir -p bin && cd bin
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz
find . -type f -name ffmpeg -executable -exec cp {} ./ffmpeg \;
find . -type f -name ffprobe -executable -exec cp {} ./ffprobe \;
cd ..
```

### 3. Backend Setup (FastAPI)
```bash
# From repository root:
python -m venv .venv
.\.venv\Scripts\activate   # On Linux/macOS: source .venv/bin/activate

cd Backend
pip install --upgrade pip
pip install -r requirements.txt

# Download default models (Embeddings & Diffusers SD 1.5)
python download_model.py --embeddings
python download_model.py --diffusers  # Or: python download_model.py --all

# Launch Backend API Server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend Setup (React + Vite)
```bash
cd Frontend
npm install
npm run dev
```

### 5. Ollama AI Setup
1. Download and install Ollama from [https://ollama.com/download](https://ollama.com/download).
2. Start the Ollama server:
   ```bash
   ollama serve
   ```
3. Pull required AI models:
   ```bash
   ollama pull qwen2.5:3b
   ollama pull gemma2:2b
   ```
4. Verify models:
   ```bash
   ollama list
   ```

### 6. Stable Diffusion Forge Setup
1. Clone Stable Diffusion WebUI Forge:
   ```bash
   mkdir C:\GEN_AI_Environment
   cd C:\GEN_AI_Environment
   git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
   cd stable-diffusion-webui-forge
   ```
2. Download a `.safetensors` model checkpoint into `models/Stable-diffusion/`, for example:
   ```powershell
   curl.exe -L -C - -o "models\Stable-diffusion\Realistic_Vision_V5.1.safetensors" "https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/resolve/main/Realistic_Vision_V5.1.safetensors"
   ```
3. **Critical NumPy Compatibility Fix**:
   Forge requires NumPy 1.x (`1.26.4`). If NumPy 2.x is installed, run inside Forge's venv:
   ```bash
   .\venv\Scripts\python.exe -m pip install "numpy==1.26.4" "opencv-contrib-python==4.8.1.78" --force-reinstall --no-cache-dir
   ```
4. Launch Forge in API mode:
   ```bash
   set COMMANDLINE_ARGS=--skip-python-version-check --api --listen --port 7860
   .\webui-user.bat
   ```

---

## 🔧 Troubleshooting & FAQ

### Issue: Forge crashes with `ValueError: numpy.dtype size changed` or `_ARRAY_API not found`
- **Cause**: Stable Diffusion Forge was launched with NumPy 2.x, which is incompatible with `torch 2.3.1` and `scikit-image 0.21`.
- **Solution**: Run `.\start.bat` or `.\download.bat` which auto-applies `:FIX_FORGE_NUMPY`, or run manually:
  ```bash
  C:\GEN_AI_Environment\stable-diffusion-webui-forge\venv\Scripts\python.exe -m pip install "numpy==1.26.4" "opencv-contrib-python==4.8.1.78" --force-reinstall --no-cache-dir
  ```

### Issue: Forge shows "You do not have any model!" or Frontend shows "Forge Offline (Preview Mode)"
- **Cause**: No `.safetensors` model is in `models/Stable-diffusion`, or Forge is not running on port 7860 with `--api`.
- **Solution**: Run `.\download.bat` to auto-download `Realistic_Vision_V5.1.safetensors`, and make sure Forge is running with `COMMANDLINE_ARGS=--api --listen --port 7860`.

### Issue: Ollama model generation hangs or times out
- **Cause**: Ollama background service is not running or model is not downloaded.
- **Solution**: Ensure `ollama serve` is running in its terminal and verify with `ollama list` that `qwen2.5:3b` and `gemma2:2b` are pulled.

---

## 📄 License
This project is licensed under the MIT License.
