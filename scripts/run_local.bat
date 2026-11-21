@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

set "HOST=127.0.0.1"
set "PORT=8501"
set "MODE_ARGS=--db data/expenses.db"
set "IS_LAN=0"

:parse_args
if "%~1"=="" goto run_app
if /I "%~1"=="--lan" (
    set "HOST=0.0.0.0"
    set "IS_LAN=1"
    shift
    goto parse_args
)
if /I "%~1"=="--demo" (
    set "MODE_ARGS=--demo"
    shift
    goto parse_args
)
shift
goto parse_args

:run_app
echo ============================================================================
echo   UNISPEND 2.0 - LICH TAI CHINH ^& TRO LY AI SINH VIEN (LOCAL SERVER)
echo ============================================================================
if "%IS_LAN%"=="1" (
    echo [CHE DO LAN WI-FI] Cho phep dien thoai cung mang Wi-Fi truy cap:
    echo   Host: %HOST%  ^|  Port: %PORT%
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do (
        set "IP_VAL=%%a"
        set "IP_VAL=!IP_VAL: =!"
        echo   Mo tren dien thoai: http://!IP_VAL!:%PORT%
    )
    echo ----------------------------------------------------------------------------
    "%PYTHON_EXE%" -m streamlit run app.py --server.address=%HOST% --server.port=%PORT% --browser.gatherUsageStats=false -- %MODE_ARGS%
) else (
    echo [CHE DO MAY TINH CA NHAN]
    echo   URL: http://127.0.0.1:%PORT%
    echo   Dung: run_local.bat --lan   ^(de mo cho dien thoai cung Wi-Fi^)
    echo   Dung: run_local.bat --demo  ^(de mo che do du lieu mau^)
    echo ----------------------------------------------------------------------------
    if "%MODE_ARGS%"=="--demo" (
        "%PYTHON_EXE%" main.py --demo
    ) else (
        "%PYTHON_EXE%" main.py --legacy
    )
)
if errorlevel 1 pause
