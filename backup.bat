@echo off
setlocal

:: Set destination to a folder inside the current directory
set "DEST=%~dp0AG_Backup"

echo ==========================================
echo    Antigravity IDE - Auto Backup
echo ==========================================
echo Destination: %DEST%
echo.

if not exist "%DEST%" mkdir "%DEST%"

echo Backing up raw chat data...
:: Check for both legacy and new folder naming conventions
if exist "%USERPROFILE%\.gemini\antigravity" (
    xcopy "%USERPROFILE%\.gemini\antigravity" "%DEST%\antigravity" /E /I /Y >nul
)
if exist "%USERPROFILE%\.gemini\antigravity-ide" (
    xcopy "%USERPROFILE%\.gemini\antigravity-ide" "%DEST%\antigravity-ide" /E /I /Y >nul
)

echo Backing up editor settings...
if exist "%APPDATA%\antigravity\User\settings.json" (
    copy "%APPDATA%\antigravity\User\settings.json" "%DEST%\settings_legacy.json" /Y >nul
)
if exist "%APPDATA%\Antigravity IDE\User\settings.json" (
    copy "%APPDATA%\Antigravity IDE\User\settings.json" "%DEST%\settings_new.json" /Y >nul
)

echo.
echo Backup complete! Safe to proceed with uninstall.
echo ==========================================
pause