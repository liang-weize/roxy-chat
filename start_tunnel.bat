@echo off
setlocal
title Roxy Cloudflare Tunnel
cd /d "%~dp0"

echo ================================================
echo   Roxy Chat - Cloudflare Tunnel
echo ================================================
echo.
echo   1. Start the website first with start.bat
echo   2. Wait a few seconds, a URL will appear below:
echo
echo        https://xxxx.trycloudflare.com
echo
echo   3. Send that URL to your friends
echo      Use the access password configured locally; never publish it.
echo
echo   NOTE: the URL changes after every PC restart.
echo
echo ================================================
echo.
tunnel\cloudflared.exe tunnel --url http://127.0.0.1:8321 --no-autoupdate
echo.
echo Tunnel disconnected (window closed or connection lost).
pause
