@echo off
cd /d %~dp0\..
call .venv\Scripts\activate.bat
if "%~1"=="" (echo Usage: RUN_BACKTEST.bat path\events.jsonl & exit /b 1)
python -m runner_genesis.cli backtest "%~1"
