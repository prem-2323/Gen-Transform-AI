@echo off
setlocal EnableDelayedExpansion
title Gen-Transform-AI - Master Setup and Launch Controller

:: Set ROOT_DIR to the directory containing this batch file (with trailing slash)
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

:: Ensure local bin directory is in PATH
if exist "%ROOT_DIR%bin" (
    set "PATH=%ROOT_DIR%bin;%PATH%"
)

cls
echo ==============================================================================
echo        GEN-TRANSFORM-AI / DOCLINK GROUNDED RAG PLATFORM
echo               Full Stack Automatic Master Launcher
echo ==============================================================================
echo.

:: -----------------------------------------------------------------------------
:: 1. FAST PREREQUISITE AND ENVIRONMENT CHECKS (< 0.2s)
:: -----------------------------------------------------------------------------
echo [*] Checking system environment...

set "HAS_GIT=0"
set "HAS_PYTHON=0"
set "HAS_NODE=0"
set "HAS_NPM=0"
set "HAS_FFMPEG=0"
set "HAS_OLLAMA=0"
set "HAS_FORGE=0"
set "FORGE_DIR="

:: Check Git
where git >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_GIT=1"
    echo   [OK] Git is available.
) else (
    echo   [WARN] Git is not installed or not in PATH!
)

:: Check Python
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_PYTHON=1"
    echo   [OK] Python is available.
) else (
    echo   [ERROR] Python is not installed or not in PATH! Please install Python 3.10+
)

:: Check Node.js
where node >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_NODE=1"
    echo   [OK] Node.js is available.
) else (
    echo   [ERROR] Node.js is not installed or not in PATH! Please install Node.js 18+
)

:: Check NPM
where npm >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_NPM=1"
    echo   [OK] NPM is available.
) else (
    echo   [ERROR] NPM is not installed or not in PATH!
)

:: Check FFmpeg & FFprobe
where ffmpeg >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_FFMPEG=1"
    echo   [OK] FFmpeg is available.
) else (
    if exist "%ROOT_DIR%bin\ffmpeg.exe" (
        set "PATH=%ROOT_DIR%bin;!PATH!"
        set "HAS_FFMPEG=1"
        echo   [OK] FFmpeg found in bin folder.
    ) else if exist "%ROOT_DIR%bin\ffmpeg" (
        set "PATH=%ROOT_DIR%bin;!PATH!"
        set "HAS_FFMPEG=1"
        echo   [OK] FFmpeg found in bin folder.
    ) else (
        echo   [INFO] FFmpeg not found on system. Auto-downloading to bin...
        call :AUTO_SETUP_FFMPEG
    )
)

:: Check Ollama
where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "HAS_OLLAMA=1"
    echo   [OK] Ollama AI service is installed.
) else (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Ollama;!PATH!"
        set "HAS_OLLAMA=1"
        echo   [OK] Ollama found in LocalAppData.
    ) else (
        echo   [INFO] Ollama not found on system. Auto-downloading...
        call :AUTO_SETUP_OLLAMA
    )
)

:: Check Stable Diffusion Forge in local project or C:\GEN_AI_Environment
if exist "%ROOT_DIR%stable-diffusion-webui-forge" (
    set "HAS_FORGE=1"
    set "FORGE_DIR=%ROOT_DIR%stable-diffusion-webui-forge"
    echo   [OK] Stable Diffusion Forge found at: !FORGE_DIR!
) else if exist "C:\GEN_AI_Environment\stable-diffusion-webui-forge" (
    set "HAS_FORGE=1"
    set "FORGE_DIR=C:\GEN_AI_Environment\stable-diffusion-webui-forge"
    echo   [OK] Stable Diffusion Forge found at: !FORGE_DIR!
) else (
    echo   [INFO] SD Forge directory not found. Auto-cloning into C:\GEN_AI_Environment...
    call :AUTO_SETUP_SD_FORGE
)

if %HAS_PYTHON% EQU 0 (
    echo.
    echo [CRITICAL ERROR] Python is required to run the Backend. Please install Python and try again.
    pause
    exit /b 1
)

if %HAS_NODE% EQU 0 (
    echo.
    echo [CRITICAL ERROR] Node.js is required to run the Frontend. Please install Node.js and try again.
    pause
    exit /b 1
)

:: -----------------------------------------------------------------------------
:: 2. AUTOMATIC FULL STACK LAUNCH (All 4 Terminals)
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo [*] Automatically Launching All 4 Terminals...
echo ==============================================================================

call :CHECK_AND_INSTALL_DEPS_IF_MISSING
call :START_OLLAMA
call :START_SD_FORGE
call :START_BACKEND
call :START_FRONTEND

:: -----------------------------------------------------------------------------
:: 3. SUCCESS SCREEN AND FAST BROWSER LAUNCH (< 3s)
:: -----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo                      GEN-TRANSFORM-AI ALL 4 SERVICES ACTIVE
echo ==============================================================================
echo   [1] Frontend Web UI:       http://localhost:5173  (Running in UI terminal)
echo   [2] Backend API:           http://localhost:8000  (Running in Backend terminal)
echo   [3] Ollama AI Service:     http://localhost:11434 (Running in Ollama terminal)
echo   [4] SD Forge Image Gen:    http://localhost:7860  (Running in Forge terminal)
echo   ----------------------------------------------------------------------------
echo   * Swagger API Docs:      http://localhost:8000/docs
echo   * Backend Health Check:  http://localhost:8000/health
echo   * FFmpeg Engine:         Available (Video & Audio Pipeline Ready)
echo ==============================================================================
echo.
echo [*] Opening Web Application in your browser (within 3 seconds)...
ping 127.0.0.1 -n 3 >nul
start http://localhost:5173

echo.
echo [INFO] All 4 terminal windows have been launched.
echo Keep the opened server command windows running while using the app.
echo Press any key to close this launcher controller window...
pause >nul
exit /b 0

:: -----------------------------------------------------------------------------
:: SUBROUTINES & HELPERS
:: -----------------------------------------------------------------------------

:AUTO_SETUP_FFMPEG
if not exist "%ROOT_DIR%bin" mkdir "%ROOT_DIR%bin" 2>nul
echo   Downloading FFmpeg for Windows...
curl.exe -L -o "%TEMP%\ffmpeg.zip" "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
if exist "%TEMP%\ffmpeg.zip" (
    echo   Extracting FFmpeg binaries to bin...
    tar -xf "%TEMP%\ffmpeg.zip" -C "%TEMP%"
    for /r "%TEMP%" %%F in (ffmpeg.exe ffprobe.exe) do (
        if exist "%%F" copy /y "%%F" "%ROOT_DIR%bin\" >nul
    )
    del "%TEMP%\ffmpeg.zip" >nul 2>&1
    if exist "%ROOT_DIR%bin\ffmpeg.exe" (
        set "PATH=%ROOT_DIR%bin;!PATH!"
        set "HAS_FFMPEG=1"
        echo   [OK] FFmpeg installed successfully into bin.
    ) else (
        echo   [WARNING] FFmpeg extraction did not find binaries.
    )
) else (
    echo   [WARN] Could not auto-download FFmpeg. Video generation may be limited.
    echo          Refer to readme.txt for manual FFmpeg setup.
)
exit /b 0

:AUTO_SETUP_OLLAMA
where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Downloading Ollama installer...
    curl.exe -L -o "%TEMP%\OllamaSetup.exe" "https://ollama.com/download/OllamaSetup.exe"
    if exist "%TEMP%\OllamaSetup.exe" (
        echo   Installing Ollama silently...
        "%TEMP%\OllamaSetup.exe" /SILENT
        ping 127.0.0.1 -n 4 >nul
        del "%TEMP%\OllamaSetup.exe" >nul 2>&1
        set "PATH=%LOCALAPPDATA%\Programs\Ollama;!PATH!"
        set "HAS_OLLAMA=1"
        echo   [OK] Ollama installed successfully.
    ) else (
        echo   [WARNING] Failed to download OllamaSetup.exe.
    )
)
exit /b 0

:AUTO_SETUP_SD_FORGE
if not defined FORGE_DIR (
    if not exist "C:\GEN_AI_Environment" (
        mkdir "C:\GEN_AI_Environment" 2>nul
    )
    if %HAS_GIT% EQU 1 (
        echo   Cloning stable-diffusion-webui-forge into C:\GEN_AI_Environment...
        cd /d "C:\GEN_AI_Environment"
        git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
        if exist "C:\GEN_AI_Environment\stable-diffusion-webui-forge" (
            set "HAS_FORGE=1"
            set "FORGE_DIR=C:\GEN_AI_Environment\stable-diffusion-webui-forge"
            echo   [OK] Cloned SD Forge into C:\GEN_AI_Environment\stable-diffusion-webui-forge
        ) else (
            echo   [WARNING] Failed to clone Stable Diffusion Forge.
        )
    ) else (
        echo   [ERROR] Git is not installed. Please install Git to auto-clone SD Forge.
    )
    cd /d "%ROOT_DIR%"
)
exit /b 0

:CHECK_AND_INSTALL_DEPS_IF_MISSING
:: Check if node_modules exists
if not exist "%ROOT_DIR%Frontend\node_modules" (
    echo [*] Frontend node_modules missing. Running npm install...
    cd /d "%ROOT_DIR%Frontend"
    call npm install
    cd /d "%ROOT_DIR%"
)

:: Probe for FastAPI, PyTorch, and SentenceTransformers
python -c "import fastapi, uvicorn, sentence_transformers, torch" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [*] Backend requirements missing. Running pip install...
    cd /d "%ROOT_DIR%Backend"
    python -m pip install -r requirements.txt
    cd /d "%ROOT_DIR%"
)

:: Pre-download and cache default embedding model 'BAAI/bge-small-en-v1.5'
python "%ROOT_DIR%Backend\download_model.py"
exit /b 0


:START_OLLAMA
if %HAS_OLLAMA% EQU 1 (
    echo [*] Launching Ollama AI Server Terminal on Port 11434...
    start "Ollama AI Server (Port 11434)" cmd /k "ollama serve"
) else (
    echo [INFO] Ollama not found - skipping Ollama terminal.
)
exit /b 0

:START_SD_FORGE
if %HAS_FORGE% EQU 1 (
    if defined FORGE_DIR (
        if exist "!FORGE_DIR!\start-image-api.bat" (
            echo [*] Launching SD Forge Image API Terminal on Port 7860...
            start "SD Forge Image API (Port 7860)" /D "!FORGE_DIR!" cmd /k "call start-image-api.bat"
        ) else if exist "!FORGE_DIR!\webui-user.bat" (
            echo [*] Launching SD Forge WebUI Terminal on Port 7860...
            start "SD Forge WebUI (Port 7860)" /D "!FORGE_DIR!" cmd /k "set COMMANDLINE_ARGS=--api --listen --port 7860 && call webui-user.bat"
        ) else if exist "!FORGE_DIR!\webui.bat" (
            echo [*] Launching SD Forge WebUI Terminal on Port 7860...
            start "SD Forge WebUI Terminal (Port 7860)" /D "!FORGE_DIR!" cmd /k "set COMMANDLINE_ARGS=--api --listen --port 7860 && call webui.bat"
        )
    )
) else (
    echo [INFO] SD Forge directory not found - skipping SD Forge terminal.
)
exit /b 0

:START_BACKEND
echo [*] Launching Backend API Server Terminal on Port 8000...
start "Backend API Server (Port 8000)" /D "%ROOT_DIR%Backend" cmd /k "set PATH=%ROOT_DIR%bin;!PATH! && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
exit /b 0

:START_FRONTEND
echo [*] Launching Frontend Dev Server Terminal on Port 5173...
start "Frontend UI (Port 5173)" /D "%ROOT_DIR%Frontend" cmd /k "npm run dev"
exit /b 0
