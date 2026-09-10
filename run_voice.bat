@echo off
setlocal
title Roxy Voice Service
cd /d "%~dp0voice-engine\GPT-SoVITS"
echo Starting GPT-SoVITS voice service on port 9880...
echo Keep this window open.
echo.
runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880
if errorlevel 1 (
  echo.
  echo Voice service stopped with an error.
  pause
)
