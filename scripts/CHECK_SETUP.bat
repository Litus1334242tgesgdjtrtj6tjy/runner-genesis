@echo off
cd /d %~dp0\..
if not exist .venv\Scripts\activate.bat (
  echo [RUNNER GENESIS] Virtual environment not found.
  echo Run scripts\INSTALL_WINDOWS.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
set LIVE_TRADING=false
python -m runner_genesis.cli doctor
pause
