@echo off
cd /d %~dp0\..
call .venv\Scripts\activate.bat
set LIVE_TRADING=false
set RUNNER_MODE=PAPER
python -m runner_genesis.cli serve --host 127.0.0.1 --port 8000
