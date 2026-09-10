@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul
if not errorlevel 1 goto use_py
python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul
if not errorlevel 1 goto use_python
if not exist "voice-engine\GPT-SoVITS\runtime\python.exe" goto missing_python
"voice-engine\GPT-SoVITS\runtime\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul
if errorlevel 1 goto missing_python
"voice-engine\GPT-SoVITS\runtime\python.exe" scripts\launch.py %*
goto finished
:use_py
py -3 scripts\launch.py %*
goto finished
:use_python
python scripts\launch.py %*
goto finished
:missing_python
echo Install Python 3.12 from https://www.python.org/downloads/windows/
echo Enable "Add python.exe to PATH", then reopen this launcher.
pause
exit /b 1
:finished
set "ROXY_EXIT=%errorlevel%"
if not "%ROXY_EXIT%"=="0" pause
exit /b %ROXY_EXIT%
