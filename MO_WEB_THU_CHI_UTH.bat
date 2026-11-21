@echo off
cd /d "%~dp0"
.\.venv\Scripts\python.exe main.py --demo
if errorlevel 1 pause
