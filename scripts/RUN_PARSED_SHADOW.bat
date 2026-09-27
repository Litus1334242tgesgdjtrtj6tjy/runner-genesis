@echo off
cd /d %~dp0\..
call .venv\Scripts\activate.bat
set LIVE_TRADING=false
set RUNNER_MODE=LIVE_SHADOW
python -m runner_genesis.cli shadow
pause
