@echo off
setlocal
cd /d %~dp0\..
py -3.11 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .[dev]
if not exist .env copy .env.example .env
python -m runner_genesis.cli demo --out data\demo\demo_events.jsonl
python -m pytest -q
pause
