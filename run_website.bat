@echo off
setlocal
title Roxy Chat Website
cd /d "%~dp0"
set "PYTHON=%~dp0voice-engine\GPT-SoVITS\runtime\python.exe"
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v ROXY_LLM_API_KEY 2^>nul') do set "ROXY_LLM_API_KEY=%%B"
echo Starting Roxy chat website on http://127.0.0.1:8321
echo Keep this window open.
echo.
if not exist "%PYTHON%" (
  echo Missing bundled Python runtime: %PYTHON%
  pause
  exit /b 1
)
if "%ROXY_LLM_API_KEY%"=="" (
  echo Missing ROXY_LLM_API_KEY. Set it in your user environment before starting.
  pause
  exit /b 1
)
"%PYTHON%" backend\main.py
if errorlevel 1 (
  echo.
  echo Website stopped with an error.
  pause
)
