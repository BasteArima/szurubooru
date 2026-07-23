"""
FastAPI wrapper exposing the WD v3 tagger over the HTTP contract szurubooru's
auto-tag `ai` method speaks:

    POST /tag                       (image bytes as the raw body, or multipart)
      header:  X-Auth-Token: <token>
      query:   general_threshold, character_threshold   (both optional)
      ->  { "model": "...",
            "rating":    { tag: score, ... },
            "general":   { tag: score, ... },   # only tags >= general_threshold
            "character": { tag: score, ... } }  # only tags >= character_threshold

    GET  /health   ->  { status, model, providers, gpu }

Config is via environment variables (see .env.example). Bind to the LAN and set
WD_AUTH_TOKEN; the token is the only thing standing between the model and anyone
on the network.
"""

import io
import logging
import os

from fastapi import FastAPI, Header, HTTPException, Query, Request
from PIL import Image

from tagger import WDTagger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("wd-tagger")

MODEL_DIR = os.environ.get(
    "WD_MODEL_DIR", os.path.join(os.path.dirname(__file__), "model")
)
AUTH_TOKEN = os.environ.get("WD_AUTH_TOKEN", "")
DEFAULT_GENERAL_THRESHOLD = float(
    os.environ.get("WD_GENERAL_THRESHOLD", "0.35")
)
DEFAULT_CHARACTER_THRESHOLD = float(
    os.environ.get("WD_CHARACTER_THRESHOLD", "0.75")
)
MAX_IMAGE_BYTES = int(os.environ.get("WD_MAX_IMAGE_BYTES", str(64 * 1024 * 1024)))

app = FastAPI(title="szurubooru WD tagger service")
_tagger = None  # type: WDTagger | None


@app.on_event("startup")
def _load_model() -> None:
    global _tagger
    _tagger = WDTagger(MODEL_DIR)
    if not _tagger.gpu:
        logger.warning(
            "CUDAExecutionProvider not active - running on CPU (slow). See the "
            "README (Blackwell / CUDA notes) or use the ComfyUI fallback."
        )
    if not AUTH_TOKEN:
        logger.warning(
            "WD_AUTH_TOKEN is empty - the /tag endpoint is UNAUTHENTICATED."
        )


def _check_auth(token: str) -> None:
    if AUTH_TOKEN and token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="invalid or missing token")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _tagger is not None else "loading",
        "model": _tagger.model_name if _tagger else None,
        "providers": _tagger.providers if _tagger else [],
        "gpu": bool(_tagger.gpu) if _tagger else False,
    }


async def _read_image_bytes(request: Request) -> bytes:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = (
            form.get("file") or form.get("content") or form.get("image")
        )
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(
                status_code=400, detail="no file field in multipart body"
            )
        return await upload.read()
    return await request.body()


@app.post("/tag")
async def tag(
    request: Request,
    x_auth_token: str = Header(default=""),
    general_threshold: float = Query(default=None),
    character_threshold: float = Query(default=None),
) -> dict:
    _check_auth(x_auth_token)
    if _tagger is None:
        raise HTTPException(status_code=503, detail="model still loading")

    data = await _read_image_bytes(request)
    if not data:
        raise HTTPException(status_code=400, detail="empty request body")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="image too large")

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception:
        raise HTTPException(status_code=400, detail="cannot decode image")

    gt = (
        general_threshold
        if general_threshold is not None
        else DEFAULT_GENERAL_THRESHOLD
    )
    ct = (
        character_threshold
        if character_threshold is not None
        else DEFAULT_CHARACTER_THRESHOLD
    )
    return _tagger.tag(image, gt, ct)
