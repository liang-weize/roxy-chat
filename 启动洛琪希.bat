@echo off
setlocal
title Roxy AI Launcher
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PY=%ROOT%voice-engine\GPT-SoVITS\runtime\python.exe"

if not exist "%PY%" (
  echo Missing bundled Python runtime. Please run setup_voice.bat first.
  pause
  exit /b 1
)

echo Starting Roxy AI...
netstat -ano | findstr /R /C:":9880 .*LISTENING" >nul
if errorlevel 1 (
  start "Roxy Voice - Keep Open" "%ComSpec%" /k call "%ROOT%run_voice.bat"
) else (
  echo Voice service already running.
)

timeout /t 3 /nobreak >nul
netstat -ano | findstr /R /C:":8321 .*LISTENING" >nul
if errorlevel 1 (
  start "Roxy Website - Keep Open" "%ComSpec%" /k call "%ROOT%run_website.bat"
) else (
  echo Chat website already running.
)

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8321"
exit /b 0
