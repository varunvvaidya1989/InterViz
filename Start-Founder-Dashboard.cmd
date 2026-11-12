@echo off
cd /d "%~dp0"
python -m founder_dashboard.server --open-browser
pause
