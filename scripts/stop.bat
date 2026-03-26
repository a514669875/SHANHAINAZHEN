@echo off
setlocal EnableExtensions
REM Stop process listening on SHANHAI_PORT (default 18080, same as start.bat).
REM Override: set SHANHAI_PORT=8000
REM ASCII-only for cmd GBK.

if not defined SHANHAI_PORT set "SHANHAI_PORT=18080"

echo Stopping listener on port %SHANHAI_PORT% ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = %SHANHAI_PORT%; Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $id = $_.OwningProcess; Write-Host ('Stop PID ' + $id + ' port ' + $p); Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }"
echo Done.
pause
