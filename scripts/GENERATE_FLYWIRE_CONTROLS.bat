@echo off
cd /d %~dp0\..
call .venv\Scripts\activate.bat
python -c "from runner_genesis.flywire.controls import generate_controls; import json; print(json.dumps(generate_controls('artifacts/flywire'), indent=2))"
