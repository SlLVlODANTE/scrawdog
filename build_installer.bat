@echo off
chcp 65001 >nul

if not exist "dist\EGoRCL0uD.exe" (
    echo [!] Build .exe first: run build.bat
    pause
    exit /b 1
)

set ISCC=
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo [!] Inno Setup not found.
    echo Download: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

echo Using: %ISCC%
"%ISCC%" installer.iss
if errorlevel 1 (
    echo [!] Build failed.
    pause
    exit /b 1
)

echo.
echo ===========================================
echo  Done!  installer\EGoRCL0uD Setup.exe
echo ===========================================
pause
