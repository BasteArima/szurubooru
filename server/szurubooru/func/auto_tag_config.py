import copy
import json
from typing import Any, Dict, Optional

from szurubooru import db, model

# sentinel the client may send back for a secret field to mean "leave unchanged"
MASK = "__unchanged__"

# dotted paths whose values are secret and must never be returned in cleartext
SECRET_FIELDS = [
    "hash.sources.rule34.apiKey",
    "hash.sources.danbooru.apiKey",
    "hash.sources.gelbooru.apiKey",
    "ai.token",
]

DEFAULTS = {
    "typeTags": {
        "enabled": True,
        "applyOnUpload": True,
        "animatedTag": "animated",
        "videoTag": "video",
        "tagCategory": "meta",
    },
    "hash": {
        "enabled": True,
        "requestDelaySeconds": 2.0,
        "userAgent": "szurubooru-autotag/1.0",
        "applySafety": False,
        "safetyOnlyIfUnset": True,
        "categoryMap": {
            "artist": "artist",
            "character": "character",
            "copyright": "copyright",
            "meta": "meta",
            "general": "general",
        },
        # enabled sources are queried in `priority` order, stop at first hit
        "sources": {
            "rule34": {
                "enabled": True,
                "priority": 1,
                "apiKey": "",
                "userId": "",
            },
            "danbooru": {
                "enabled": True,
                "priority": 2,
                "login": "",
                "apiKey": "",
            },
            "gelbooru": {
                "enabled": False,
                "priority": 3,
                "apiKey": "",
                "userId": "",
            },
        },
    },
    "ai": {
        "enabled": False,
        "url": "",
        "token": "",
        "generalThreshold": 0.35,
        "characterThreshold": 0.75,
        "resize": True,
    },
}


def _normalize(cfg: Dict) -> Dict:
    """Coerce older shapes to the current schema (settings persist as a blob)."""
    hash_cfg = cfg.setdefault("hash", {})
    sources = hash_cfg.get("sources")
    if not isinstance(sources, dict):
        # old format was an ordered list of source names
        sources = {}
    normalized = {}
    for key, default in DEFAULTS["hash"]["sources"].items():
        given = sources.get(key)
        normalized[key] = _deep_merge(
            default, given if isinstance(given, dict) else {}
        )
    hash_cfg["sources"] = normalized
    # migrate legacy top-level danbooru credentials into the source block
    for legacy, target in (
        ("danbooruLogin", "login"),
        ("danbooruApiKey", "apiKey"),
    ):
        if hash_cfg.get(legacy) and not normalized["danbooru"].get(target):
            normalized["danbooru"][target] = hash_cfg[legacy]
        hash_cfg.pop(legacy, None)
    return cfg


def _deep_merge(base: Dict, override: Optional[Dict]) -> Dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _path_get(cfg: Dict, dotted: str) -> Any:
    node = cfg  # type: Any
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _path_set(cfg: Dict, dotted: str, value: Any) -> None:
    node = cfg
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _get_row() -> Optional[model.AutoTagConfig]:
    return db.session.query(model.AutoTagConfig).first()


def get_config() -> Dict[str, Any]:
    """Full config including secrets, with defaults merged in."""
    row = _get_row()
    stored = {}  # type: Dict[str, Any]
    if row and row.value:
        try:
            stored = json.loads(row.value)
        except ValueError:
            stored = {}
    return _normalize(_deep_merge(DEFAULTS, stored))


def get_public_config() -> Dict[str, Any]:
    """Config for the API: secret fields replaced with a boolean 'is set'."""
    cfg = get_config()
    for path in SECRET_FIELDS:
        _path_set(cfg, path, bool(_path_get(cfg, path)))
    return cfg


def update_config(incoming: Dict[str, Any]) -> Dict[str, Any]:
    current = get_config()
    merged = _normalize(_deep_merge(current, incoming or {}))
    # keep an existing secret if the client echoed the mask / a boolean back
    for path in SECRET_FIELDS:
        new_value = _path_get(merged, path)
        if isinstance(new_value, bool) or new_value == MASK:
            _path_set(merged, path, _path_get(current, path))
    row = _get_row()
    if not row:
        row = model.AutoTagConfig()
        db.session.add(row)
    row.value = json.dumps(merged)
    db.session.flush()
    return get_public_config()
