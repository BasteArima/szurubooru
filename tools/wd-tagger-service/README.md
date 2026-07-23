# szurubooru WD tagger service

A small standalone microservice that runs the **WD v3 tagger** (SmilingWolf) on
a GPU PC and answers the HTTP contract szurubooru's auto-tag **`ai`** method
speaks. It is **not** part of the szurubooru server/client Docker images — it
runs on your GPU machine and is turned on on-demand before an AI-tagging batch.

szurubooru is agnostic to what is behind the URL: this FastAPI service is the
primary path, and **ComfyUI** (WD14 node) is a documented fallback that speaks
the same contract (see below).

---

## HTTP contract

```
POST /tag
  header:  X-Auth-Token: <token>                     (if WD_AUTH_TOKEN is set)
  body:    the raw image bytes            (Content-Type: image/*)
           - or - multipart/form-data with a `file` field
  query:   general_threshold, character_threshold    (both optional floats)

  200 ->  {
            "model": "wd-vit-large-tagger-v3",
            "rating":    { "general": 0.82, "sensitive": 0.15, ... },
            "general":   { "1girl": 0.99, "long_hair": 0.88, ... },   # >= general_threshold
            "character": { "hatsune_miku": 0.97, ... }                # >= character_threshold
          }

GET /health -> { "status": "ok", "model": "...", "providers": [...], "gpu": true }
```

`rating` is always the full set (4 values); `general` and `character` contain
only tags at or above the given thresholds.

---

## Requirements

- An NVIDIA GPU + recent driver. Tested target: **RTX 5070 Ti (Blackwell,
  sm_120), CUDA 12.8**.
- **Python 3.10–3.12**.
- ~2 GB free VRAM (the WD v3 models are small).

## Install

```bash
cd tools/wd-tagger-service
python -m venv venv
# Windows:  venv\Scripts\activate
# Linux:    source venv/bin/activate
pip install -r requirements.txt
```

### ⚠️ Blackwell / CUDA 12.8 notes (read this)

`onnxruntime-gpu` from PyPI must match your **CUDA toolkit version**, and this
is the #1 gotcha.

**Symptom (CUDA-version mismatch):** startup logs something like
```
Error loading "...onnxruntime_providers_cuda.dll" which depends on
"cublasLt64_13.dll" which is missing.
Failed to create CUDAExecutionProvider. Require cuDNN 9.* and CUDA 13.*
... providers=['CPUExecutionProvider']
```
`cublasLt64_13.dll` is a **CUDA 13** library. It means pip installed the newest
`onnxruntime-gpu` (1.23+, built for CUDA 13) while you have **CUDA 12.8**. The
service then falls back to CPU.

**Fix (use a CUDA 12 build):**
```bash
pip install --force-reinstall "onnxruntime-gpu>=1.20,<1.23"
```
(requirements.txt already pins this; the `--force-reinstall` replaces a 1.23+
that a previous run may have pulled.) Then make sure **CUDA 12.8** and
**cuDNN 9** DLLs are on your `PATH`.

**Verify:** `GET /health` → `"gpu": true` (startup log also prints the active
providers).

**If the CUDA provider still won't initialise** (kernels not built for sm_120,
missing cuDNN, etc.) the service keeps running on **CPU** — fine for testing and
light use, slow for a large backfill. For guaranteed GPU on the 50-series, use
the **ComfyUI fallback** below (your ComfyUI already runs on this card).

The service never crashes on a missing GPU — it degrades to CPU and warns.

## Download the model

```bash
python download_model.py
```

Pulls `model.onnx` + `selected_tags.csv` into `./model`. Pick a model via
`WD_MODEL_REPO` (see the top of `download_model.py`):

| repo | notes |
|------|-------|
| `SmilingWolf/wd-vit-large-tagger-v3` | balanced (default) |
| `SmilingWolf/wd-eva02-large-tagger-v3` | highest quality, a little slower |
| `SmilingWolf/wd-swinv2-tagger-v3` | fast |

## Configure & run

Copy `.env.example` to `.env` and set at least `WD_AUTH_TOKEN`. Then:

```bash
# Windows
run.bat
# Linux / macOS
./run.sh
# or directly
python -m uvicorn app:app --env-file .env --host 0.0.0.0 --port 7860
```

### Config (env vars)

| var | default | meaning |
|-----|---------|---------|
| `WD_AUTH_TOKEN` | *(empty)* | shared secret; empty = **no auth** (LAN only) |
| `WD_MODEL_DIR` | `./model` | dir with `model.onnx` + `selected_tags.csv` |
| `WD_MODEL_REPO` | `SmilingWolf/wd-vit-large-tagger-v3` | download source |
| `WD_GENERAL_THRESHOLD` | `0.35` | default general threshold |
| `WD_CHARACTER_THRESHOLD` | `0.75` | default character threshold |
| `WD_HOST` / `WD_PORT` | `0.0.0.0` / `7860` | bind address / port |
| `WD_MAX_IMAGE_BYTES` | `67108864` | reject bodies larger than this |

## Smoke test

```bash
curl http://localhost:7860/health

curl -s -X POST "http://localhost:7860/tag?general_threshold=0.35&character_threshold=0.75" \
     -H "X-Auth-Token: <your-token>" \
     --data-binary @some_image.jpg | python -m json.tool
```

---

## Hooking it up to szurubooru

In the szurubooru **Auto-tag** admin tab, AI tagger section:

- **Service URL**: `http://<gpu-pc-lan-ip>:7860/tag`
- **Token**: the same value as `WD_AUTH_TOKEN`
- thresholds: general ≈ 0.35, character ≈ 0.75

(The szuru-side `ai` method that calls this is the next delivery step; until it
is wired, this service can be exercised directly with `curl`.)

## Start-before-a-batch checklist

1. Power on the GPU PC.
2. `cd tools/wd-tagger-service` → activate the venv → `run.bat` / `./run.sh`.
3. `curl .../health` → confirm `"gpu": true`.
4. In szurubooru, run an auto-tag job with the **AI** method enabled.
5. Stop the service when the batch is done.

---

## GPU on Blackwell via ComfyUI's Python (recommended if plain pip won't)

If `onnxruntime-gpu` from pip won't drive the 50-series (CUDA-version hell), the
easiest fix is **not** an adapter — it's to run *this* service with **ComfyUI's
Python**, which already has an onnxruntime-gpu that works on your card (that's
why WD tagging works inside ComfyUI). Same service, same contract, just a
different interpreter.

1. Make sure WD tagging actually runs on the GPU inside ComfyUI first (the
   **WD14 Tagger** node, `pythongosssss/ComfyUI-WD14-Tagger`; watch the ComfyUI
   console / Task Manager GPU during a tag). If ComfyUI itself tags on CPU, this
   won't help — fix ComfyUI's onnxruntime first.

2. Find ComfyUI's Python:
   - portable build: `...\ComfyUI_windows_portable\python_embeded\python.exe`
   - a venv/conda ComfyUI: that env's `python`.

3. Install this service's non-CUDA deps into that Python **without touching its
   onnxruntime** (numpy/pillow are already there):
   ```powershell
   & "C:\path\to\python_embeded\python.exe" -m pip install fastapi "uvicorn[standard]" huggingface_hub python-multipart
   ```
   (Verify it has onnxruntime-gpu: `python_embeded\python.exe -c "import onnxruntime as o; print(o.get_available_providers())"` should list `CUDAExecutionProvider`.)

4. Run this service with that Python:
   ```powershell
   set PYTHON=C:\path\to\python_embeded\python.exe
   run.bat
   ```
   `GET /health` should now show `"gpu": true`. szurubooru keeps pointing at the
   same `http://<pc>:7860/tag` — nothing changes on the szuru side.

### Alternative: a ComfyUI-API adapter (only if the above can't work)

If you must go through ComfyUI's own server instead, put a thin adapter in front
of ComfyUI's `/prompt` API: it accepts the `POST /tag` request, uploads the
image (`/upload/image`), queues a *Load Image → WD14 Tagger* workflow
(`/prompt`), polls `/history/{id}`, then reshapes the node's tag output into the
`{model, rating, general, character}` JSON (categorise the flat tag list with
`selected_tags.csv`). More moving parts than reusing ComfyUI's Python above.

## Security

- Bind to the LAN and **set `WD_AUTH_TOKEN`**. The token is the only gate.
- Do not expose the port to the internet.
- The service only reads images and returns tags; it writes nothing.
