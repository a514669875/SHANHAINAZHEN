@echo off
setlocal EnableExtensions
REM ShanHaiNaZhen desktop service: API + static UI (single machine).
REM Default port 18080 (8000 is often taken). Override: set SHANHAI_PORT=8000
REM ASCII-only for cmd GBK.

if not defined SHANHAI_PORT set "SHANHAI_PORT=18080"

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\backend"
set "PY=%BACKEND%\venv\Scripts\python.exe"

cd /d "%BACKEND%"
if errorlevel 1 goto ERR_CD
if not exist "%PY%" goto ERR_VENV

echo.
echo ========================================
echo   ShanHaiNaZhen  :%SHANHAI_PORT%  (API + Web UI)
echo ========================================
echo   Local:  http://127.0.0.1:%SHANHAI_PORT%
echo   LAN:    http://THIS-PC-IPv4:%SHANHAI_PORT%
echo.
echo   Port override:  set SHANHAI_PORT=8000  before start.bat
echo   No web page? Run:  scripts\build_release.bat
echo ========================================
echo.

"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port %SHANHAI_PORT%
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
echo In folder "backend" run:  python -m venv venv
echo Then:  venv\Scripts\activate  and  pip install -r requirements.txt
pause
exit /b 1

:ERR_UVICORN
echo.
echo ERROR: Server stopped. Code: %EC%
pause
exit /b %EC%

:END
endlocal
exit /b 0
