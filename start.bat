@echo off
rem ==============================================================================
rem  AI Friend — Windows Double-Click Launcher
rem ==============================================================================
title AI Friend Launcher
echo ==============================================================================
echo                      AI FRIEND — WINDOWS LAUNCHER
echo ==============================================================================
echo.

where powershell >nul 2>nul
if %ERRORLEVEL% equ 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
) else (
    echo [ERROR] PowerShell is required to run the automated startup scripts.
    pause
)
