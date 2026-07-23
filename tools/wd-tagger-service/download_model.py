"""
Download a WD v3 tagger (model.onnx + selected_tags.csv) from HuggingFace into
the model dir the service reads.

    python download_model.py

Override the repo / target via env vars:
    WD_MODEL_REPO   default SmilingWolf/wd-vit-large-tagger-v3
    WD_MODEL_DIR    default ./model

Good picks (all small, <2 GB VRAM):
    SmilingWolf/wd-vit-large-tagger-v3     - balanced (default)
    SmilingWolf/wd-eva02-large-tagger-v3   - highest quality, a bit slower
    SmilingWolf/wd-swinv2-tagger-v3        - fast
"""

import os

from huggingface_hub import hf_hub_download

REPO = os.environ.get("WD_MODEL_REPO", "SmilingWolf/wd-vit-large-tagger-v3")
OUT = os.environ.get(
    "WD_MODEL_DIR", os.path.join(os.path.dirname(__file__), "model")
)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for filename in ("model.onnx", "selected_tags.csv"):
        print("downloading %s from %s ..." % (filename, REPO))
        path = hf_hub_download(repo_id=REPO, filename=filename, local_dir=OUT)
        print("  ->", path)
    print("done. model dir:", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
