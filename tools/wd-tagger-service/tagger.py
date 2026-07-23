"""
WD v3 tagger (SmilingWolf) inference wrapped for the szurubooru auto-tag `ai`
method. Pure onnxruntime + Pillow + numpy; no heavy ML framework.

The model dir must contain `model.onnx` and `selected_tags.csv` (both live in
the SmilingWolf HuggingFace repos — see download_model.py).
"""

import csv
import logging
import os
from typing import Dict, List

import numpy as np
import onnxruntime as ort
from PIL import Image

logger = logging.getLogger("wd-tagger")

# selected_tags.csv category ids used by the WD taggers
_RATING_CATEGORY = 9
_CHARACTER_CATEGORY = 4
# everything else (0 = general, and any future ids) is treated as general


def _select_providers() -> List[str]:
    """Prefer CUDA; always keep CPU as a fallback so the service still starts
    if the GPU execution provider fails to initialise (e.g. an onnxruntime
    build that does not yet support the card)."""
    available = ort.get_available_providers()
    providers = []  # type: List[str]
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    providers.append("CPUExecutionProvider")
    return providers


class WDTagger:
    def __init__(self, model_dir: str) -> None:
        model_path = os.path.join(model_dir, "model.onnx")
        tags_path = os.path.join(model_dir, "selected_tags.csv")
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                "model.onnx not found in %r - run download_model.py first"
                % model_dir
            )
        if not os.path.exists(tags_path):
            raise FileNotFoundError(
                "selected_tags.csv not found in %r - run download_model.py"
                % model_dir
            )

        self.model_name = os.path.basename(os.path.abspath(model_dir))
        self.session = ort.InferenceSession(
            model_path, providers=_select_providers()
        )
        self.providers = self.session.get_providers()
        self.gpu = "CUDAExecutionProvider" in self.providers

        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        # WD taggers are NHWC: [batch, H, W, 3]; H may be dynamic -> default 448
        height = input_meta.shape[1] if len(input_meta.shape) == 4 else None
        self.target_size = height if isinstance(height, int) else 448

        self._load_tags(tags_path)
        logger.info(
            "loaded %s | providers=%s | input=%dpx | tags=%d",
            self.model_name,
            self.providers,
            self.target_size,
            len(self.tag_names),
        )

    def _load_tags(self, path: str) -> None:
        self.tag_names = []  # type: List[str]
        self.rating_idx = []  # type: List[int]
        self.general_idx = []  # type: List[int]
        self.character_idx = []  # type: List[int]
        with open(path, newline="", encoding="utf-8") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                self.tag_names.append(row["name"])
                try:
                    category = int(row["category"])
                except (KeyError, ValueError):
                    category = 0
                if category == _RATING_CATEGORY:
                    self.rating_idx.append(index)
                elif category == _CHARACTER_CATEGORY:
                    self.character_idx.append(index)
                else:
                    self.general_idx.append(index)

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        # flatten transparency onto white, then pad to a white square
        image = image.convert("RGBA")
        canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image)
        image = canvas.convert("RGB")

        width, height = image.size
        side = max(width, height)
        square = Image.new("RGB", (side, side), (255, 255, 255))
        square.paste(image, ((side - width) // 2, (side - height) // 2))
        if side != self.target_size:
            square = square.resize(
                (self.target_size, self.target_size), Image.BICUBIC
            )

        array = np.asarray(square, dtype=np.float32)
        # WD taggers expect BGR, values in 0-255 (NOT normalised to 0-1)
        array = array[:, :, ::-1]
        return np.expand_dims(array, axis=0)

    def tag(
        self,
        image: Image.Image,
        general_threshold: float,
        character_threshold: float,
    ) -> Dict:
        batch = self._preprocess(image)
        preds = self.session.run(None, {self.input_name: batch})[0][0]

        rating = {
            self.tag_names[i]: float(preds[i]) for i in self.rating_idx
        }
        general = {
            self.tag_names[i]: float(preds[i])
            for i in self.general_idx
            if preds[i] >= general_threshold
        }
        character = {
            self.tag_names[i]: float(preds[i])
            for i in self.character_idx
            if preds[i] >= character_threshold
        }
        return {
            "model": self.model_name,
            "rating": rating,
            "general": general,
            "character": character,
        }
