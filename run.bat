@echo off
setlocal
rem Run PyDownloader straight from the sources in this folder.
rem The .venv (or uv) runs the code from src, so no reinstall is needed.
title PyDownloader
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"

if exist "%~dp0.venv\Scripts\python.exe" goto venv

where uv >nul 2>nul
if not errorlevel 1 goto uv

echo [PyDownloader] Neither .venv nor uv was found.
echo Create the environment first:  uv sync
echo.
pause
exit /b 1

:venv
echo [PyDownloader] Starting from .venv: python -m pydownloader %*
"%~dp0.venv\Scripts\python.exe" -m pydownloader %*
set "code=%errorlevel%"
goto done

:uv
echo [PyDownloader] Starting through uv ...
uv run --project "%~dp0." python -m pydownloader %*
set "code=%errorlevel%"
goto done

:done
if not "%code%"=="0" (
    echo.
    echo [PyDownloader] Exited with error, code %code%.
    pause
)
exit /b %code%