@echo off
setlocal
cd /d "%~dp0system"
rem Trial UI only. The normal launcher starts desktop_app.py.
set "PYW=C:\Users\1180075\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
set "PYTHON=%PYW:pythonw.exe=python.exe%"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" ui_preview.py
if errorlevel 1 pause