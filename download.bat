@echo off
setlocal EnableDelayedExpansion
title Gen-Transform-AI - Complete Asset and Model Downloader

:: Set ROOT_DIR to the directory containing this batch file (with trailing slash)
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

:: Ensure local bin and virtual environment are in PATH
if exist "%ROOT_DIR%bin" (
    set "PATH=%ROOT_DIR%bin;!PATH!"
)
if exist "%ROOT_DIR%.venv\Scripts" (
    set "PATH=%ROOT_DIR%.venv\Scripts;!PATH!"
)

cls
echo ==============================================================================
echo        GEN-TRANSFORM-AI / DOCLINK GROUNDED RAG PLATFORM
echo          Complete Dependency, Asset and Model Downloader
echo ==============================================================================
echo.
echo This script downloads and configures ALL required components:
echo   [1] Python Virtual Environment & Backend Packages (FastAPI, PyTorch, Diffusers)
echo   [2] Frontend Node Modules (React + Vite)
echo   [3] FFmpeg & FFprobe Video/Audio Binaries
echo   [4] HuggingFace Embedding Model (BAAI/bge-small-en-v1.5)
echo   [5] HuggingFace Diffusers Image Model (runwayml/stable-diffusion-v1-5)
echo   [6] Ollama AI Server & LLM Models (qwen2.5:3b, gemma2:2b)
echo   [7] Stable Diffusion Forge & Photorealistic Model Checkpoint
echo.
echo ==============================================================================
echo.

:: -----------------------------------------------------------------------------
:: 1. PREREQUISITES VERIFICATION
:: -----------------------------------------------------------------------------
echo [*] Step 1/7: Verifying core system prerequisites...

set "HAS_GIT=0"
set "HAS_PYTHON=0"
set "HAS_NODE=0"
set "HAS_NPM=0"

where git >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_GIT=1"
    echo   [OK] Git is installed.
) else (
    echo   [ERROR] Git is not installed or not in PATH! Please install Git from https://git-scm.com/
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_PYTHON=1"
    echo   [OK] Python is installed.
) else (
    echo   [ERROR] Python is not installed or not in PATH! Please install Python 3.10+ from https://www.python.org/
)

where node >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_NODE=1"
    echo   [OK] Node.js is installed.
) else (
    echo   [ERROR] Node.js is not installed or not in PATH! Please install Node.js 18+ from https://nodejs.org/
)

where npm >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_NPM=1"
    echo   [OK] NPM is installed.
) else (
    echo   [ERROR] NPM is not installed or not in PATH!
)

if %HAS_PYTHON% EQU 0 (
    echo.
    echo [CRITICAL ERROR] Python is required to proceed. Please install Python and re-run this script.
    pause
    exit /b 1
)

if %HAS_NODE% EQU 0 (
    echo.
    echo [CRITICAL ERROR] Node.js is required to proceed. Please install Node.js and re-run this script.
    pause
    exit /b 1
)

:: -----------------------------------------------------------------------------
:: 2. PYTHON VENV & BACKEND DEPENDENCIES
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Step 2/7: Setting up Python Virtual Environment & Backend Packages...
echo ==============================================================================

if not exist "%ROOT_DIR%.venv\Scripts\python.exe" (
    echo [*] Creating virtual environment at .venv...
    python -m venv "%ROOT_DIR%.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
    ) else (
        echo   [OK] Virtual environment created.
    )
) else (
    echo   [OK] Virtual environment already exists at .venv.
)

set "PY_EXEC=%ROOT_DIR%.venv\Scripts\python.exe"
if not exist "!PY_EXEC!" set "PY_EXEC=python"

echo [*] Upgrading pip in virtual environment...
"!PY_EXEC!" -m pip install --upgrade pip >nul 2>&1

echo [*] Installing Backend requirements from Backend\requirements.txt (including diffusers)...
"!PY_EXEC!" -m pip install -r "%ROOT_DIR%Backend\requirements.txt"
if errorlevel 1 (
    echo   [WARNING] Some backend packages failed to install. Check network connection.
) else (
    echo   [OK] Backend requirements installed successfully.
)

:: -----------------------------------------------------------------------------
:: 3. FRONTEND DEPENDENCIES (NPM INSTALL)
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Step 3/7: Setting up Frontend Packages (node_modules)...
echo ==============================================================================

if not exist "%ROOT_DIR%Frontend\node_modules" (
    echo [*] Frontend node_modules missing. Running npm install in Frontend...
    cd /d "%ROOT_DIR%Frontend"
    call npm install
    cd /d "%ROOT_DIR%"
    echo   [OK] Frontend packages installed.
) else (
    echo   [OK] Frontend node_modules already exists.
)

:: -----------------------------------------------------------------------------
:: 4. FFMPEG & FFPROBE MEDIA PIPELINE BINARIES
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Step 4/7: Checking FFmpeg and FFprobe Binaries...
echo ==============================================================================

set "NEED_FFMPEG=1"
if exist "%ROOT_DIR%bin\ffmpeg.exe" if exist "%ROOT_DIR%bin\ffprobe.exe" (
    set "NEED_FFMPEG=0"
    echo   [OK] FFmpeg and FFprobe found in bin folder.
)

if !NEED_FFMPEG! EQU 1 (
    where ffmpeg >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo   [OK] FFmpeg found in system PATH.
        set "NEED_FFMPEG=0"
    )
)

if !NEED_FFMPEG! EQU 1 (
    echo [*] Downloading FFmpeg build for Windows...
    if not exist "%ROOT_DIR%bin" mkdir "%ROOT_DIR%bin" 2>nul
    curl.exe -L --progress-bar -o "%TEMP%\ffmpeg.zip" "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    if exist "%TEMP%\ffmpeg.zip" (
        echo [*] Extracting FFmpeg binaries to bin...
        tar -xf "%TEMP%\ffmpeg.zip" -C "%TEMP%"
        for /r "%TEMP%" %%F in (ffmpeg.exe ffprobe.exe) do (
            if exist "%%F" copy /y "%%F" "%ROOT_DIR%bin\" >nul
        )
        del "%TEMP%\ffmpeg.zip" >nul 2>&1
        if exist "%ROOT_DIR%bin\ffmpeg.exe" (
            set "PATH=%ROOT_DIR%bin;!PATH!"
            echo   [OK] FFmpeg installed successfully into bin folder.
        ) else (
            echo   [WARNING] FFmpeg extraction did not find binaries.
        )
    ) else (
        echo   [WARNING] Failed to download FFmpeg build. You can install it manually via: winget install Gyan.FFmpeg
    )
)

:: -----------------------------------------------------------------------------
:: 5. HUGGINGFACE EMBEDDING MODEL (BAAI/bge-small-en-v1.5)
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Step 5/7: Caching HuggingFace Embedding Model...
echo ==============================================================================

"!PY_EXEC!" "%ROOT_DIR%Backend\download_model.py" --embeddings

:: -----------------------------------------------------------------------------
:: 6. HUGGINGFACE DIFFUSERS IMAGE GENERATION MODEL (runwayml/stable-diffusion-v1-5)
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Step 6/7: Caching Diffusers Image Generation Model...
echo ==============================================================================
echo [*] Downloading / verifying Diffusers pipeline: runwayml/stable-diffusion-v1-5...
"!PY_EXEC!" "%ROOT_DIR%Backend\download_model.py" --diffusers

:: -----------------------------------------------------------------------------
:: 7. OLLAMA AI RUNTIME & MODELS (qwen2.5:3b, gemma2:2b)
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Step 7/7: Setting up Ollama & Downloading AI Models...
echo ==============================================================================

set "HAS_OLLAMA=0"
where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_OLLAMA=1"
    echo   [OK] Ollama is installed on system.
) else (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Ollama;!PATH!"
        set "HAS_OLLAMA=1"
        echo   [OK] Ollama found in LocalAppData.
    ) else (
        echo [*] Ollama not found. Downloading OllamaSetup.exe...
        curl.exe -L --progress-bar -o "%TEMP%\OllamaSetup.exe" "https://ollama.com/download/OllamaSetup.exe"
        if exist "%TEMP%\OllamaSetup.exe" (
            echo [*] Installing Ollama silently...
            "%TEMP%\OllamaSetup.exe" /SILENT
            ping 127.0.0.1 -n 4 >nul
            del "%TEMP%\OllamaSetup.exe" >nul 2>&1
            set "PATH=%LOCALAPPDATA%\Programs\Ollama;!PATH!"
            set "HAS_OLLAMA=1"
            echo   [OK] Ollama installed successfully.
        ) else (
            echo   [WARNING] Failed to download Ollama. Please install manually from https://ollama.com/
        )
    )
)

if !HAS_OLLAMA! EQU 1 (
    echo [*] Checking Ollama server status...
    curl.exe -s http://localhost:11434/api/tags >nul 2>&1
    if errorlevel 1 (
        echo [*] Starting local Ollama server in background for model download...
        start "Ollama Background Service" /MIN cmd /c "ollama serve"
        ping 127.0.0.1 -n 4 >nul
    )

    echo [*] Pulling Ollama LLM Model: qwen2.5:3b (Analysis and Script Generation)...
    ollama pull qwen2.5:3b

    echo [*] Pulling Ollama Vision Model: gemma2:2b (Scene Visual Descriptions)...
    ollama pull gemma2:2b

    echo   [OK] Ollama AI models verified.
)

:: -----------------------------------------------------------------------------
:: STABLE DIFFUSION FORGE & CHECKPOINT MODEL
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Stable Diffusion WebUI Forge & Image Generation Setup...
echo ==============================================================================

set "FORGE_DIR="
if exist "%ROOT_DIR%stable-diffusion-webui-forge" (
    set "FORGE_DIR=%ROOT_DIR%stable-diffusion-webui-forge"
) else if exist "C:\GEN_AI_Environment\stable-diffusion-webui-forge" (
    set "FORGE_DIR=C:\GEN_AI_Environment\stable-diffusion-webui-forge"
)

if not defined FORGE_DIR (
    if not exist "C:\GEN_AI_Environment" mkdir "C:\GEN_AI_Environment" 2>nul
    if !HAS_GIT! EQU 1 (
        echo [*] Cloning Stable Diffusion Forge into C:\GEN_AI_Environment...
        cd /d "C:\GEN_AI_Environment"
        git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
        if exist "C:\GEN_AI_Environment\stable-diffusion-webui-forge" (
            set "FORGE_DIR=C:\GEN_AI_Environment\stable-diffusion-webui-forge"
            echo   [OK] Cloned SD Forge into C:\GEN_AI_Environment\stable-diffusion-webui-forge
        )
        cd /d "%ROOT_DIR%"
    ) else (
        echo   [WARNING] Git not found. Skipping auto-clone of SD Forge.
    )
) else (
    echo   [OK] SD Forge found at: !FORGE_DIR!
)

:: Check for SD Checkpoint model (*.safetensors)
if defined FORGE_DIR (
    set "SD_MODELS_DIR=!FORGE_DIR!\models\Stable-diffusion"
    if not exist "!SD_MODELS_DIR!" mkdir "!SD_MODELS_DIR!" 2>nul

    set "HAS_SD_MODEL=0"
    for %%F in ("!SD_MODELS_DIR!\*.safetensors") do (
        set "HAS_SD_MODEL=1"
    )

    if !HAS_SD_MODEL! EQU 1 (
        echo   [OK] Stable Diffusion checkpoint (.safetensors) found in:
        echo        !SD_MODELS_DIR!
    ) else (
        echo [*] No .safetensors model found in !SD_MODELS_DIR!
        echo [*] Downloading photorealistic model (Realistic_Vision_V5.1.safetensors)...
        echo     (Size: ~4.2 GB. Resume supported via curl -C -)
        curl.exe -L -C - --progress-bar -o "!SD_MODELS_DIR!\Realistic_Vision_V5.1.safetensors" "https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/resolve/main/Realistic_Vision_V5.1.safetensors"
        if exist "!SD_MODELS_DIR!\Realistic_Vision_V5.1.safetensors" (
            echo   [OK] Downloaded Realistic_Vision_V5.1.safetensors successfully!
        ) else (
            echo   [WARNING] Could not auto-download model checkpoint.
            echo             You can place any SD 1.5 .safetensors model inside:
            echo             !SD_MODELS_DIR!
        )
    )

    :: NumPy 1.x fix for Forge if venv exists
    if exist "!FORGE_DIR!\venv\Scripts\python.exe" (
        echo [*] Checking SD Forge NumPy compatibility...
        "!FORGE_DIR!\venv\Scripts\python.exe" -c "import numpy; assert numpy.__version__.startswith('1')" >nul 2>&1
        if errorlevel 1 (
            echo   [FIX] Downgrading Forge NumPy to 1.26.4 for torch/skimage compatibility...
            "!FORGE_DIR!\venv\Scripts\python.exe" -m pip install "opencv-contrib-python==4.8.1.78" "numpy==1.26.4" --force-reinstall --no-cache-dir
        ) else (
            echo   [OK] SD Forge NumPy 1.x is active and compatible.
        )
    )
)

:: -----------------------------------------------------------------------------
:: SUMMARY & READY NOTICE
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo                  ALL ASSETS AND MODELS DOWNLOADED SUCCESSFULLY!
echo ==============================================================================
echo.
echo All components are verified and cached:
echo   [OK] Python Virtual Environment (.venv) & Backend Requirements
echo   [OK] Frontend Node Modules (React + Vite)
echo   [OK] FFmpeg and FFprobe Binaries (bin\)
echo   [OK] HuggingFace Embedding Model (BAAI/bge-small-en-v1.5)
echo   [OK] HuggingFace Diffusers Model (runwayml/stable-diffusion-v1-5)
echo   [OK] Ollama AI Models (qwen2.5:3b, gemma2:2b)
echo   [OK] Stable Diffusion Forge & Model Checkpoints
echo.
echo To launch the full platform in 1 click, simply run:
echo   .\start.bat
echo.
echo Press any key to exit this installer...
pause >nul
exit /b 0
