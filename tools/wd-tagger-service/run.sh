#!/usr/bin/env bash
# Start the WD tagger service. Config is read from .env.
set -euo pipefail
cd "$(dirname "$0")"
set -a
[ -f .env ] && . ./.env
set +a
# set PYTHON to ComfyUI's interpreter to reuse its working onnxruntime-gpu
exec "${PYTHON:-python}" -m uvicorn app:app \
    --host "${WD_HOST:-0.0.0.0}" \
    --port "${WD_PORT:-7860}"
