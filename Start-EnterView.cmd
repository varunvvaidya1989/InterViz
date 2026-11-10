@echo off
cd /d "%~dp0"
python start.py --open-browser
if errorlevel 1 pause
