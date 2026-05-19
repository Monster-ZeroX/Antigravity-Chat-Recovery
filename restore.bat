@echo off
setlocal

set "SRC=%~dp0AG_Backup"

echo ==========================================
echo    Antigravity IDE - Clean Restore
echo ==========================================
echo.

if not exist "%SRC%" (
    echo ERROR: Backup folder not found. Please run 1_backup.bat first.
    pause
    exit /b
)

echo 1. Restoring raw chat data into new architecture...
if not exist "%USERPROFILE%\.gemini" mkdir "%USERPROFILE%\.gemini"

:: Prioritize restoring to the modern folder naming convention
if exist "%SRC%\antigravity-ide" (
    xcopy "%SRC%\antigravity-ide" "%USERPROFILE%\.gemini\antigravity-ide" /E /I /Y >nul
) else if exist "%SRC%\antigravity" (
    xcopy "%SRC%\antigravity" "%USERPROFILE%\.gemini\antigravity-ide" /E /I /Y >nul
)

echo 2. Restoring user settings (and blocking updates)...
if not exist "%APPDATA%\Antigravity IDE\User" mkdir "%APPDATA%\Antigravity IDE\User"

if exist "%SRC%\settings_new.json" (
    copy "%SRC%\settings_new.json" "%APPDATA%\Antigravity IDE\User\settings.json" /Y >nul
) else if exist "%SRC%\settings_legacy.json" (
    copy "%SRC%\settings_legacy.json" "%APPDATA%\Antigravity IDE\User\settings.json" /Y >nul
)

:: Append the update block to the settings file just in case
echo. >> "%APPDATA%\Antigravity IDE\User\settings.json"
echo "update.mode": "none" >> "%APPDATA%\Antigravity IDE\User\settings.json"

echo.
echo NOTICE: Corrupted databases were intentionally skipped.
echo ==========================================
echo Restore Complete! You may now run fix_chats.py
echo ==========================================
pause