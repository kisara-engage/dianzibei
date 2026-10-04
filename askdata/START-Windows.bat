@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   Explainable NL2SQL / RAG Agent - Launcher
echo ============================================
echo.

REM ---- 1. Check Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.10+ from:
    echo     https://www.python.org/downloads/
    echo IMPORTANT: check "Add python.exe to PATH" during install.
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [ERROR] Python version too old, need 3.10 or newer.
    python -V
    pause
    exit /b 1
)
echo [1/3] Python OK
python -V

REM ---- 2. Warn if working folder path contains non-ASCII characters ----
python -c "import os,sys; p=os.getcwd(); sys.exit(1 if any(ord(c)>127 for c in p) else 0)"
if errorlevel 1 (
    echo.
    echo [WARN] This folder path contains non-ASCII characters:
    echo        %CD%
    echo        It normally still works, but if anything fails,
    echo        move this whole folder to an English path, e.g. D:\askdata
    echo.
)

REM ---- 3. Try to install optional dependencies (never fatal) ----
echo [2/3] Optional dependencies (jieba / flask / PyYAML)...
python -c "import sys;sys.exit(0 if all(__import__(m) for m in ('jieba','flask','yaml')) else 1)" 2>nul
if errorlevel 1 (
    echo      Not installed yet. Trying to fetch from mirror, 30s timeout...
    python -m pip install -q -r requirements.txt ^
        -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 15 --retries 1 2>nul
    if errorlevel 1 (
        python -m pip install -q -r requirements.txt --timeout 15 --retries 1 2>nul
    )
    python -c "import sys;sys.exit(0 if all(__import__(m) for m in ('jieba','flask','yaml')) else 1)" 2>nul
    if errorlevel 1 (
        echo      [INFO] Could not reach PyPI. That is fine --
        echo             the app runs on the Python standard library alone.
        echo             Retrieval quality is slightly lower without jieba.
    ) else (
        echo      Optional dependencies installed.
    )
) else (
    echo      Already available.
)

REM ---- 4. Create the llm_config.yaml on first run ----
if not exist "llm_config.yaml" (
    if exist "llm_config.example.yaml" copy llm_config.example.yaml llm_config.yaml >nul
)

echo [3/3] Configuration check...
python -c "import sys;sys.path.insert(0,'.');from askdata.config import load_model_config,is_placeholder_key;b,k,m=load_model_config();sys.exit(0 if (b and m and not is_placeholder_key(k)) else 1)" 2>nul
if errorlevel 1 (
    echo.
    echo ============================================
    echo   [ACTION NEEDED] No LLM API key configured
    echo ============================================
    echo.
    echo   A model API key is required to answer questions.
    echo.
    echo   Step 1: get a key - DeepSeek, ~10 CNY is plenty:
    echo       https://platform.deepseek.com/
    echo   Step 2: paste it into llm_config.yaml
    echo.
    echo   llm_config.yaml has been created for you and will
    echo   open in Notepad now. Replace the api_key value
    echo   ^(keep the quotes off^), save, then run this again.
    echo.
    notepad llm_config.yaml
    pause
    exit /b 0
)

echo      Config OK
echo.
echo ============================================
echo   Starting... browser will open automatically
echo   Press Ctrl+C to stop the server
echo ============================================
echo.

REM ---- Open browser after the server has time to boot ----
start "" cmd /c "timeout /t 5 >nul && start http://127.0.0.1:8788"

python -m askdata.server

echo.
echo Server stopped.
pause
