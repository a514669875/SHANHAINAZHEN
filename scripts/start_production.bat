@echo off
setlocal EnableExtensions
REM Production: API + static UI on port 8000
REM NOTE: This file must stay ASCII-only so cmd.exe (GBK) parses it correctly.

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\backend"
set "PY=%BACKEND%\venv\Scripts\python.exe"

cd /d "%BACKEND%"
if errorlevel 1 goto ERR_CD
if not exist "%PY%" goto ERR_VENV

echo.
echo ========================================
echo   ShanHaiNaZhen  production  :8000
echo ========================================
echo   Browser: http://127.0.0.1:8000
echo   LAN:     http://THIS-PC-IP:8000
echo   No login page? Run:
echo     scripts\build_package_assets.bat
echo     scripts\sync_dist_to_backend_web.bat
echo ========================================
echo.

"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" goto ERR_UVICORN
goto END

:ERR_CD
echo ERROR: Cannot open folder:
echo   %BACKEND%
echo Keep this file in:  your_project\scripts\
pause
exit /b 1

:ERR_VENV
echo ERROR: venv not found:
echo   %PY%
echo In folder "backend" create venv and: pip install -r requirements.txt
echo See README.md
pause
exit /b 1

:ERR_UVICORN
echo.
echo ERROR: Server stopped. Code: %EC%
echo Copy the red text above for your IT helper.
pause
exit /b %EC%

:END
endlocal
exit /b 0
