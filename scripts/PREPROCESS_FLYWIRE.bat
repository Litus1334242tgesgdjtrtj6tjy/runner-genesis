@echo off
cd /d %~dp0\..
call .venv\Scripts\activate.bat
if "%~1"=="" (echo Usage: PREPROCESS_FLYWIRE.bat path\connections_princeton.csv.gz & exit /b 1)
python -m runner_genesis.cli flywire-preprocess "%~1" --out artifacts\flywire --max-nodes 20000 --min-syn-count 2
