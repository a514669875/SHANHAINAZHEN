@echo off
setlocal EnableExtensions
REM Copy frontend\dist to backend\web\dist. ASCII-only for cmd GBK.

cd /d "%~dp0.."
if not exist "frontend\dist\index.html" (
    echo ERROR: frontend\dist\index.html not found. Run scripts\build_package_assets.bat first.
    pause
    exit /b 1
)
if not exist "backend\web\dist\" mkdir "backend\web\dist"
xcopy /E /I /Y "frontend\dist\*" "backend\web\dist\"
if errorlevel 1 (
    echo ERROR: xcopy failed
    pause
    exit /b 1
)
echo OK: copied to backend\web\dist
pause
