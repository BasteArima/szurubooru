@echo off
REM Start the WD tagger service. Edit host/port here; other config in .env.
REM
REM To run on the GPU by reusing ComfyUI's Python (which already has a working
REM onnxruntime-gpu for your CUDA / Blackwell), point PYTHON at it before
REM running, e.g.:
REM   set PYTHON=D:\ComfyUI_windows_portable\python_embeded\python.exe
REM   run.bat
setlocal
if "%PYTHON%"=="" set PYTHON=python
if "%WD_HOST%"=="" set WD_HOST=0.0.0.0
if "%WD_PORT%"=="" set WD_PORT=7860
"%PYTHON%" -m uvicorn app:app --env-file .env --host %WD_HOST% --port %WD_PORT%
