@echo off
cd /d "%~dp0"
title Antigravity Floating Monitor

:: Launch with pyw
start "" "%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe" floating_widget.py 2>nul
if %errorlevel% equ 0 exit /b 0

start "" pyw floating_widget.py 2>nul
if %errorlevel% equ 0 exit /b 0

:: Fallback to pythonw
start "" pythonw floating_widget.py 2>nul
if %errorlevel% equ 0 exit /b 0

:: Fallback to py with feedback
py floating_widget.py
pause
