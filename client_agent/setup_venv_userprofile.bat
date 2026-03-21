@echo off
REM 在用户目录下创建 venv，避免工程在同步盘/杀毒重点扫描路径时卡死
setlocal
set "VENVDIR=%LOCALAPPDATA%\ShanHaiNaZhen_client_venv"
cd /d "%~dp0"

echo.
echo 将在以下目录创建虚拟环境（约需 1~5 分钟，杀毒软件可能拖慢）:
echo   %VENVDIR%
echo.

if exist "%VENVDIR%\Scripts\python.exe" (
  echo 已存在可用 venv，跳过创建。若要重建请先手动删除该文件夹。
  goto :done
)

where py >nul 2>&1
if %errorlevel%==0 (
  echo 使用 py 启动器（优先 3.12）...
  py -3.12 -m venv "%VENVDIR%"
  if errorlevel 1 py -3.11 -m venv "%VENVDIR%"
  if errorlevel 1 py -3 -m venv "%VENVDIR%"
) else (
  python -m venv "%VENVDIR%"
)

if not exist "%VENVDIR%\Scripts\python.exe" (
  echo.
  echo [失败] 未能创建 venv。请尝试：关闭杀毒对 %%LOCALAPPDATA%% 的实时扫描、或换 Python 3.11/3.12。
  pause
  exit /b 1
)

call "%VENVDIR%\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r "%~dp0requirements.txt"
echo.
echo [完成] venv 已就绪，请使用 run_user_venv.bat 启动服务。

:done
pause
