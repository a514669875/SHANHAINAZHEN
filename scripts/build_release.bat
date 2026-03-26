@echo off
setlocal EnableExtensions
REM Single-step: Vite production build + mirror to backend\web\dist (SPA served by start.bat port, default 18080).
REM Requires Node.js on this machine. ASCII-only for cmd GBK.

set "ROOT=%~dp0.."
set "FE=%ROOT%\frontend"
set "OUT=%ROOT%\backend\web\dist"

cd /d "%FE%"
if errorlevel 1 (
  echo ERROR: Cannot cd to frontend
  pause
  exit /b 1
)

if not exist "node_modules\" (
  echo Running npm install ...
  call npm install
  if errorlevel 1 exit /b 1
)

echo.
echo [1/2] npm run build:pack ...
call npm run build:pack
if errorlevel 1 exit /b 1

if not exist "%ROOT%\frontend\dist\index.html" (
  echo ERROR: frontend\dist\index.html missing after build.
  pause
  exit /b 1
)

echo.
echo [2/2] Sync to backend\web\dist ...
if not exist "%OUT%" mkdir "%OUT%"
robocopy "%ROOT%\frontend\dist" "%OUT%" /MIR /NFL /NDL /NJH /NJS /NC /NS /NP
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
  echo ERROR: robocopy failed code %RC%
  pause
  exit /b 1
)

echo.
echo OK: backend\web\dist is ready.
echo Start system: scripts\start.bat
echo.
pause
endlocal
exit /b 0
