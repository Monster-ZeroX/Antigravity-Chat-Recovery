@echo off
echo ==========================================
echo    Antigravity IDE - Deep Purge
echo ==========================================
echo.

echo 1. Force-closing Antigravity...
taskkill /F /IM antigravity.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo 2. Deleting corrupted cache and UI storage...
rmdir /S /Q "%APPDATA%\antigravity" 2>nul
rmdir /S /Q "%APPDATA%\Antigravity IDE" 2>nul

echo 3. Deleting raw chat directories...
rmdir /S /Q "%USERPROFILE%\.gemini\antigravity" 2>nul
rmdir /S /Q "%USERPROFILE%\.gemini\antigravity-ide" 2>nul

echo.
echo ==========================================
echo Purge Complete! Your system is clean.
echo ==========================================
pause