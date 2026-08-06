@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD=python"
python --version >nul 2>&1
if errorlevel 1 set "PYTHON_CMD=C:\Users\1180075\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON_CMD%" if "%PYTHON_CMD%" NEQ "python" (
  echo Python could not be found. Install Python 3.12 or later.
  pause
  exit /b 1
)
"%PYTHON_CMD%" app.py import-price --pdf "input\分割支払金一覧.pdf"
if errorlevel 1 exit /b %errorlevel%
"%PYTHON_CMD%" app.py generate --request "data\test_quote.json"
if errorlevel 1 exit /b %errorlevel%
echo.
echo Test completed. Check the ..\output folder.
pause
