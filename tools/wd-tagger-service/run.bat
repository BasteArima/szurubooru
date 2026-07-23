@echo off
REM Start the WD tagger service. Edit host/port here; other config in .env.
setlocal
if "%WD_HOST%"=="" set WD_HOST=0.0.0.0
if "%WD_PORT%"=="" set WD_PORT=7860
python -m uvicorn app:app --env-file .env --host %WD_HOST% --port %WD_PORT%
