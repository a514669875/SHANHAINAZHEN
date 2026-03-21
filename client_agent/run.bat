@echo off
REM cmd 下必须用 activate.bat；检测 Scripts\python.exe 避免半成品 venv 误判
cd /d %~dp0
if not exist "venv\Scripts\python.exe" (
    echo 正在创建虚拟环境 venv（首次可能需数分钟，Windows 杀毒会明显拖慢）...
    echo 若长时间无响应，请阅读 client_agent\README.md 或改用 setup_venv_userprofile.bat
    python -m venv venv
    if errorlevel 1 (
        echo 创建失败。可尝试: py -3.12 -m venv venv
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)
echo 启动客户端文件服务 8001 ...
uvicorn app.main:app --host 0.0.0.0 --port 8001
pause
