@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON=C:\Users\1180075\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set "VENV=%~dp0work\build-venv"
set "DIST=%~dp0..\portable"
set "BUILD_NAME=QuoteBatchApp"
set "DATA_SRC=%~dp0data"
set "ASSETS_SRC=%~dp0assets"

echo [1/5] Creating a project-local build environment...
echo      (First run can take a few minutes)
if not exist "%VENV%\Scripts\python.exe" (
  "%PYTHON%" -m venv "%VENV%"
  if errorlevel 1 goto :error
)

echo [2/5] Installing build tools into the project folder...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo [3/5] Building a portable Windows application...
if not exist "%DATA_SRC%\company.json" (
  echo.
  echo ERROR: system\data\company.json がありません。
  echo        現場の TEL/FAX 表記のため、ビルド前に company.example.json を
  echo        company.json にコピーし、正しい部署連絡先を入れてください。
  echo        （Git にはコミットしないこと）
  echo.
  goto :error
)
if not exist "%ASSETS_SRC%" mkdir "%ASSETS_SRC%"
"%VENV%\Scripts\python.exe" "%~dp0_check_company_for_portable.py"
if errorlevel 1 goto :error
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name "%BUILD_NAME%" --contents-directory system --distpath "%DIST%\build" --workpath "%~dp0work\pyinstaller" --specpath "%~dp0work" --collect-all pdfplumber --collect-all reportlab --add-data "%DATA_SRC%;data" --add-data "%ASSETS_SRC%;assets" desktop_app.py
if errorlevel 1 goto :error

echo [4/5] Arranging the user-facing folder layout...
"%VENV%\Scripts\python.exe" "%~dp0_arrange_portable.py"
if errorlevel 1 goto :error

echo [5/5] Done.
echo.
echo See the arrange script output above for the final folder path.
echo.
pause
exit /b 0

:error
echo.
echo Build failed.
pause
exit /b 1
