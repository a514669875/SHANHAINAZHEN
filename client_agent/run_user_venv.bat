@echo off
REM 使用 %LOCALAPPDATA%\ShanHaiNaZhen_client_venv 中的虚拟环境启动（需先运行 setup_venv_userprofile.bat）
setlocal
set "VENVDIR=%LOCALAPPDATA%\ShanHaiNaZhen_client_venv"
cd /d "%~dp0"

if not exist "%VENVDIR%\Scripts\python.exe" (
  echo 未找到用户目录下的 venv，请先运行: setup_venv_userprofile.bat
  pause
  exit /b 1
)

call "%VENVDIR%\Scripts\activate.bat"
pip install -q -r requirements.txt
echo 客户端文件服务: http://0.0.0.0:8001  (本机访问可用 http://127.0.0.1:8001/health)
uvicorn app.main:app --host 0.0.0.0 --port 8001
pause
