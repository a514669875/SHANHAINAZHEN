@echo off
setlocal EnableExtensions
REM Vite build only (no vue-tsc). ASCII-only for cmd GBK.

cd /d "%~dp0..\frontend"
if not exist "node_modules\" (
    echo Running npm install ...
    call npm install
    if errorlevel 1 exit /b 1
)
call npm run build:pack
if errorlevel 1 exit /b 1
echo.
echo OK: frontend\dist
echo Next: scripts\sync_dist_to_backend_web.bat
pause
