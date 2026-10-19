@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows_indic_rendering.ps1"
if errorlevel 1 (
  echo.
  echo Setup did not complete. Read the error above.
  pause
  exit /b 1
)
echo.
echo Restart Final-Shorts now so the renderer loads FriBiDi.
pause
