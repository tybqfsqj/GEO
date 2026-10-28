@echo off
chcp 65001 >nul
echo 正在启动 GEO 监控仪表盘...
cd /d "%~dp0"

:: 检查是否安装了依赖
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo 首次运行，安装依赖包...
    pip install -r requirements.txt
)

python run_server.py
pause
