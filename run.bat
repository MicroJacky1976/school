@echo off
chcp 65001 >nul
REM Windows 启动脚本

cd /d "%~dp0"

REM 检查 python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python，请先安装 Python 3 并加入 PATH
    pause
    exit /b 1
)

REM 检查并安装依赖
python -c "import pgzero, pygame" 2>nul
if %errorlevel% neq 0 (
    echo 正在安装依赖 pgzero 和 pygame...
    pip install pgzero pygame
    if %errorlevel% neq 0 (
        echo 依赖安装失败，请手动执行: pip install pgzero pygame
        pause
        exit /b 1
    )
)

python main.py
if %errorlevel% neq 0 (
    echo.
    echo 程序异常退出
    pause
)
