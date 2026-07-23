"""
Read-only clients for looking up a post by its MD5 on external boorus and
returning normalized tags + safety.

Everything goes through a shared, per-source rate limiter so a large backfill
cannot hammer a booru into an IP ban. Only the standard library is used.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# canonical booru tag categories; the config maps these onto szuru categories
CATEGORIES = ["general", "artist", "character", "copyright", "meta"]

# Gelbooru-style integer tag types -> canonical category
_GELBOORU_TYPE = {
    0: "general",
    1: "artist",
    3: "copyright",
    4: "character",
    5: "meta",
}

_RATING = {
    "s": "safe",
    "safe": "safe",
    "g": "safe",
    "general": "safe",
    "sensitive": "sketchy",
    "q": "sketchy",
    "questionable": "sketchy",
    "e": "unsafe",
    "explicit": "unsafe",
}


class BooruError(Exception):
    pass


class BooruRetryError(BooruError):
    """A transient failure (rate limit / server error) worth retrying."""


class _RateLimiter:
    def __init__(self) -> None:
        self._locks = {}  # type: Dict[str, threading.Lock]
        self._last = {}  # type: Dict[str, float]
        self._guard = threading.Lock()

    def wait(self, source: str, delay: float) -> None:
        with self._guard:
            lock = self._locks.setdefault(source, threading.Lock())
        with lock:
            now = time.monotonic()
            elapsed = now - self._last.get(source, 0.0)
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last[source] = time.monotonic()


_rate_limiter = _RateLimiter()


def _fetch(url: str, user_agent: str, source: str, delay: float) -> bytes:
    _rate_limiter.wait(source, max(0.0, float(delay)))
    request = urllib.request.Request(url)
    request.add_header(
        "User-Agent", user_agent or "szurubooru-autotag/1.0"
    )
    request.add_header("Accept", "application/json")
    # NB: never log `url` — it contains the api_key
    logger.info("booru %s: requesting", source)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read()
        logger.info(
            "booru %s: %d bytes in %.1fs",
            source,
            len(data),
            time.monotonic() - started,
        )
        return data
    except urllib.error.HTTPError as ex:
        if ex.code == 429 or ex.code >= 500:
            raise BooruRetryError(
                "%s returned HTTP %d" % (source, ex.code)
            )
        if ex.code in (401, 403):
            raise BooruError(
                "%s returned HTTP %d (auth/credentials?)" % (source, ex.code)
            )
        if ex.code == 404:
            return b""
        raise BooruError("%s returned HTTP %d" % (source, ex.code))
    except urllib.error.URLError as ex:
        raise BooruRetryError("%s unreachable: %s" % (source, ex))


def _fetch_json(url: str, user_agent: str, source: str, delay: float):
    raw = _fetch(url, user_agent, source, delay)
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return None


def _norm_safety(rating: Optional[str]) -> Optional[str]:
    if not rating:
        return None
    return _RATING.get(str(rating).strip().lower())


def _gelbooru_style(
    base_url: str,
    md5: str,
    cfg: Dict,
    source: str,
    extra: str = "",
) -> Optional[Dict]:
    ua = cfg["userAgent"]
    delay = cfg["requestDelaySeconds"]
    post_url = (
        base_url
        + "?page=dapi&s=post&q=index&json=1&limit=1&tags=md5:%s%s"
        % (urllib.parse.quote(md5), extra)
    )
    data = _fetch_json(post_url, ua, source, delay)
    posts = _extract_posts(data)
    if not posts:
        return None
    post = posts[0]
    tag_names = str(post.get("tags", "")).split()
    if not tag_names:
        return None
    categories = _gelbooru_tag_categories(
        base_url, tag_names, cfg, source, extra
    )
    tags = [(name, categories.get(name, "general")) for name in tag_names]
    return {
        "tags": tags,
        "safety": _norm_safety(post.get("rating")),
    }


def _extract_posts(data) -> List[Dict]:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    # some Gelbooru endpoints wrap posts in {"post": [...]}
    if isinstance(data, dict):
        posts = data.get("post")
        if isinstance(posts, list):
            return posts
        if isinstance(posts, dict):
            return [posts]
    return []


def _gelbooru_tag_categories(
    base_url: str, names: List[str], cfg: Dict, source: str, extra: str
) -> Dict[str, str]:
    """One extra request to resolve tag -> category for a batch of names."""
    result = {}  # type: Dict[str, str]
    if not names:
        return result
    url = (
        base_url
        + "?page=dapi&s=tag&q=index&json=1&limit=%d&names=%s%s"
        % (len(names), urllib.parse.quote(" ".join(names)), extra)
    )
    try:
        data = _fetch_json(url, cfg["userAgent"], source, cfg[
            "requestDelaySeconds"
        ])
    except BooruError:
        return result
    entries = data
    if isinstance(data, dict):
        entries = data.get("tag", [])
    if not isinstance(entries, list):
        return result
    for entry in entries:
        try:
            result[entry["name"]] = _GELBOORU_TYPE.get(
                int(entry.get("type", 0)), "general"
            )
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _source_cfg(cfg: Dict, source: str) -> Dict:
    sources = cfg.get("sources") or {}
    value = sources.get(source)
    return value if isinstance(value, dict) else {}


def _auth_extra(source_cfg: Dict) -> str:
    """Gelbooru-style &api_key=&user_id= auth, only when both are set."""
    api_key = source_cfg.get("apiKey") or ""
    user_id = source_cfg.get("userId") or ""
    if api_key and user_id:
        return "&api_key=%s&user_id=%s" % (
            urllib.parse.quote(api_key),
            urllib.parse.quote(str(user_id)),
        )
    return ""


def _lookup_rule34(md5: str, cfg: Dict) -> Optional[Dict]:
    extra = _auth_extra(_source_cfg(cfg, "rule34"))
    return _gelbooru_style(
        "https://api.rule34.xxx/index.php", md5, cfg, "rule34", extra
    )


def _lookup_gelbooru(md5: str, cfg: Dict) -> Optional[Dict]:
    extra = _auth_extra(_source_cfg(cfg, "gelbooru"))
    return _gelbooru_style(
        "https://gelbooru.com/index.php", md5, cfg, "gelbooru", extra
    )


def _lookup_danbooru(md5: str, cfg: Dict) -> Optional[Dict]:
    src = _source_cfg(cfg, "danbooru")
    login = src.get("login") or ""
    api_key = src.get("apiKey") or ""
    auth = ""
    if login and api_key:
        auth = "&login=%s&api_key=%s" % (
            urllib.parse.quote(login),
            urllib.parse.quote(api_key),
        )
    url = "https://danbooru.donmai.us/posts.json?md5=%s%s" % (
        urllib.parse.quote(md5),
        auth,
    )
    data = _fetch_json(
        url, cfg["userAgent"], "danbooru", cfg["requestDelaySeconds"]
    )
    posts = _extract_posts(data)
    if not posts:
        return None
    post = posts[0]
    tags = []  # type: List[Tuple[str, str]]
    field_map = {
        "tag_string_general": "general",
        "tag_string_artist": "artist",
        "tag_string_character": "character",
        "tag_string_copyright": "copyright",
        "tag_string_meta": "meta",
    }
    for field, category in field_map.items():
        for name in str(post.get(field, "")).split():
            tags.append((name, category))
    if not tags:
        for name in str(post.get("tag_string", "")).split():
            tags.append((name, "general"))
    if not tags:
        return None
    return {"tags": tags, "safety": _norm_safety(post.get("rating"))}


_LOOKUPS = {
    "rule34": _lookup_rule34,
    "gelbooru": _lookup_gelbooru,
    "danbooru": _lookup_danbooru,
}


def lookup(source: str, md5: str, cfg: Dict) -> Optional[Dict]:
    """Return {'tags': [(name, category)], 'safety': ...} or None if not found.

    Raises BooruRetryError on transient failures and BooruError otherwise.
    """
    fn = _LOOKUPS.get(source)
    if not fn:
        raise BooruError("Unknown booru source: %r" % source)
    return fn(md5, cfg)
