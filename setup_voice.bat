@echo off
setlocal enabledelayedexpansion
title 洛琪希语音引擎安装

REM ============================================================
REM  GPT-SoVITS 一键安装脚本 (洛琪希语音引擎)
REM  1. 下载 7zr.exe 解压工具
REM  2. 从 hf-mirror 下载 GPT-SoVITS v2pro 整合包 (约8GB, 国内直连)
REM  3. 解压并给出启动指引 (支持断点续传, 中断后重跑即可)
REM ============================================================

set "PKG_URL=https://hf-mirror.com/lj1995/GPT-SoVITS-windows-package/resolve/main/GPT-SoVITS-v2pro-20250604.7z"
set "PKG_FILE=GPT-SoVITS-v2pro-20250604.7z"
set "INSTALL_DIR=%~dp0voice-engine"
set "PROXY=http://127.0.0.1:7897"

echo.
echo ============================================
echo   GPT-SoVITS 语音引擎安装 (洛琪希音色)
echo   安装位置: %INSTALL_DIR%
echo   注意: 下载约 8GB, 请耐心等待; 中断后重新运行可续传
echo ============================================
echo.

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM ---- 第 1 步: 下载 7zr.exe ----
if exist "%INSTALL_DIR%\7zr.exe" (
    echo [1/3] 7zr.exe 已存在, 跳过
    goto step2
)
echo [1/3] 下载解压工具 7zr.exe ...
curl -fsSL -m 120 -o "%INSTALL_DIR%\7zr.exe" "https://www.7-zip.org/a/7zr.exe"
if not exist "%INSTALL_DIR%\7zr.exe" (
    echo       直连失败, 尝试代理 ...
    curl -fsSL -m 120 -x %PROXY% -o "%INSTALL_DIR%\7zr.exe" "https://www.7-zip.org/a/7zr.exe"
)
if not exist "%INSTALL_DIR%\7zr.exe" (
    echo 错误: 7zr.exe 下载失败, 请检查网络后重新运行本脚本
    pause
    exit /b 1
)

REM ---- 第 2 步: 下载整合包 (支持断点续传) ----
:step2
if exist "%INSTALL_DIR%\GPT-SoVITS\go-api.bat" (
    echo [2/3] 已检测到解压完成的 GPT-SoVITS, 跳过下载
    goto step3
)
echo [2/3] 下载 GPT-SoVITS 整合包 (约8GB)...
echo        直连失败会自动换用本地代理 %PROXY% 续传
echo.
curl -fL -C - --retry 10 --retry-delay 3 --retry-all-errors --connect-timeout 20 -m 7200 -o "%INSTALL_DIR%\%PKG_FILE%" "%PKG_URL%"
if errorlevel 1 (
    echo.
    echo       直连下载中断, 尝试走代理续传 ...
    curl -fL -C - --retry 10 --retry-delay 3 --retry-all-errors --connect-timeout 20 -m 7200 -x %PROXY% -o "%INSTALL_DIR%\%PKG_FILE%" "%PKG_URL%"
    if errorlevel 1 (
        echo.
        echo 错误: 下载失败。重新运行本脚本可从断点继续, 已下载的部分不会丢失
        pause
        exit /b 1
    )
)

REM ---- 第 3 步: 解压 ----
:step3
echo.
echo [3/3] 解压中 (约需 5-15 分钟, 请勿关闭窗口) ...
"%INSTALL_DIR%\7zr.exe" x -y -o"%INSTALL_DIR%" "%INSTALL_DIR%\%PKG_FILE%" >nul
if errorlevel 1 (
    echo 错误: 解压失败, 可能下载不完整。请删除 voice-engine 下的 .7z 文件后重跑本脚本
    pause
    exit /b 1
)
del "%INSTALL_DIR%\%PKG_FILE%"

echo.
echo ============================================
echo   安装完成! 后续步骤:
echo   1. 打开文件夹  %INSTALL_DIR%\GPT-SoVITS
echo   2. 双击运行 go-api.bat (首次弹出确认框选"是")
echo   3. 窗口出现 9880 字样即启动成功, 保持窗口开着
echo   4. 双击 start.bat 启动网站, 和洛琪希聊天!
echo ============================================
echo.
pause
