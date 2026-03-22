@echo off
setlocal EnableExtensions
set PYTHONUTF8=1

cd /d "%~dp0.."
set "ROOT_DIR=%CD%"
set "ICON_PATH=%ROOT_DIR%\src\elvar_icon.ico"
set "EXT_TEMPLATE_DIR=%ROOT_DIR%\extension"

echo [1/6] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [2/6] Installing pinned requirements...
python -m pip install --requirement requirements.txt
if errorlevel 1 goto :fail

echo [3/6] Verifying dependency consistency...
python -m pip check
if errorlevel 1 goto :fail

echo [4/6] Ensuring app icon exists...
if not exist "%ICON_PATH%" (
    echo Missing icon file: %ICON_PATH%
    goto :fail
)

if not exist "%EXT_TEMPLATE_DIR%\manifest.json" (
    echo Missing extension templates at %EXT_TEMPLATE_DIR%
    goto :fail
)

echo [5/6] Cleaning previous build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Elvar.spec del /q Elvar.spec

echo [6/6] Building executable with PyInstaller...
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "Elvar" --icon "%ICON_PATH%" --add-data "%ICON_PATH%;." --add-data "%EXT_TEMPLATE_DIR%;templates\extension" --collect-all customtkinter --distpath dist --workpath build --specpath . "src\elvar.py"
if errorlevel 1 goto :fail

if not exist "dist\Elvar\Elvar.exe" (
    echo Expected executable not found at dist\Elvar\Elvar.exe
    goto :fail
)

echo Executable ready: dist\Elvar\Elvar.exe

echo Attempting to compile Inno Setup installer...
where iscc >nul 2>nul
if errorlevel 1 (
    echo ISCC was not found in PATH. Skipping installer compile.
    echo Install Inno Setup and run: iscc scripts\elvar_installer.iss
    goto :success
)

iscc scripts\elvar_installer.iss
if errorlevel 1 goto :fail

echo Installer ready in dist\installer\

:success
echo Done.
pause
exit /b 0

:fail
echo Build failed.
pause
exit /b 1
