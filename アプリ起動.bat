@echo off
setlocal
cd /d "%~dp0system"
set "PYTHONW=C:\Users\1180075\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if not exist "%PYTHONW%" set "PYTHONW=pythonw"
start "" "%PYTHONW%" desktop_app.py
