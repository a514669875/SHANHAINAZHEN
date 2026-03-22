@echo off
setlocal EnableExtensions
REM Stop process listening on port 8000 (backend). ASCII-only for cmd GBK.

echo Stopping listener on port 8000 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = 8000; Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $id = $_.OwningProcess; Write-Host ('Stop PID ' + $id + ' port ' + $p); Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }"
echo Done.
pause
