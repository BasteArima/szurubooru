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
import xml.etree.ElementTree as ET
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

# Which sources' tag endpoint supports the plural `names=` batch lookup.
# rule34.xxx is a Gelbooru 0.2 fork: its tag endpoint returns XML (never JSON,
# even with json=1) and only honours the singular `name=` param, so categories
# must be resolved one tag at a time. gelbooru.com supports the batched lookup.
# Unknown sources default to per-tag (the safe, always-correct path).
_TAG_BATCH_SUPPORT = {
    "rule34": False,
    "gelbooru": True,
}


class _InProcessTagCategoryCache:
    """Default cache used when no persistent cache is injected (single-source
    of the .get/.put interface booru.py relies on). Kept for the life of the
    process, so it still avoids re-querying a tag within one run; the DB-backed
    cache in booru_cache.TagCategoryCache adds cross-run persistence."""

    def __init__(self) -> None:
        self._data = {}  # type: Dict[Tuple[str, str], str]
        self._lock = threading.Lock()

    def get(self, source: str, names) -> Dict[str, str]:
        with self._lock:
            return {
                name: self._data[(source, name)]
                for name in names
                if (source, name) in self._data
            }

    def put(self, source: str, mapping: Dict[str, str]) -> None:
        with self._lock:
            for name, category in mapping.items():
                self._data[(source, name)] = category


_default_tag_category_cache = _InProcessTagCategoryCache()

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
    category_cache=None,
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
        base_url, tag_names, cfg, source, extra, category_cache
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


def _parse_tag_types(raw: bytes) -> Dict[str, str]:
    """Map tag name -> canonical category from a Gelbooru-style tag listing,
    accepting either JSON (gelbooru.com) or XML (rule34.xxx)."""
    result = {}  # type: Dict[str, str]
    if not raw:
        return result
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return result

    entries = None  # type: Optional[List[Dict]]
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if data is not None:
        if isinstance(data, dict):
            data = data.get("tag", [])
        if isinstance(data, list):
            entries = data
    if entries is None:
        # XML fallback: <tags><tag type=".." name=".."/>...</tags>
        try:
            root = ET.fromstring(text)
            entries = [dict(el.attrib) for el in root.iter("tag")]
        except ET.ParseError:
            entries = []

    for entry in entries:
        try:
            name = entry["name"]
            category = _GELBOORU_TYPE.get(
                int(entry.get("type", 0)), "general"
            )
        except (KeyError, TypeError, ValueError):
            continue
        if name:
            result[name] = category
    return result


def _gelbooru_tag_categories(
    base_url: str,
    names: List[str],
    cfg: Dict,
    source: str,
    extra: str,
    category_cache=None,
) -> Dict[str, str]:
    """Resolve tag -> category, serving from the cache first and querying the
    booru's tag endpoint only for the tags not yet cached.

    gelbooru.com resolves the whole batch in one request; rule34.xxx has no
    batch param and returns XML, so it is resolved one tag at a time.
    """
    result = {}  # type: Dict[str, str]
    if not names:
        return result
    cache = category_cache or _default_tag_category_cache
    ua = cfg["userAgent"]
    delay = cfg["requestDelaySeconds"]

    result.update(cache.get(source, names))
    uncached = [name for name in names if name not in result]
    if not uncached:
        return result

    resolved = {}  # type: Dict[str, str]
    if _TAG_BATCH_SUPPORT.get(source, False):
        url = (
            base_url
            + "?page=dapi&s=tag&q=index&json=1&limit=%d&names=%s%s"
            % (len(uncached), urllib.parse.quote(" ".join(uncached)), extra)
        )
        try:
            resolved = _parse_tag_types(_fetch(url, ua, source, delay))
        except BooruError as ex:
            logger.warning("tag categories %s (batch): %s", source, ex)
    else:
        for name in uncached:
            url = (
                base_url
                + "?page=dapi&s=tag&q=index&json=1&limit=1&name=%s%s"
                % (urllib.parse.quote(name), extra)
            )
            try:
                raw = _fetch(url, ua, source, delay)
                resolved.update(_parse_tag_types(raw))
            except BooruError as ex:
                # degrade gracefully: an unresolved tag falls back to general
                logger.warning("tag category %s %r: %s", source, name, ex)

    if resolved:
        # only cache tags we actually resolved; an unresolved tag stays out of
        # the cache so a later run can retry it instead of learning "general"
        cache.put(source, resolved)
    for name in uncached:
        result[name] = resolved.get(name, "general")
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


def _lookup_rule34(
    md5: str, cfg: Dict, category_cache=None
) -> Optional[Dict]:
    extra = _auth_extra(_source_cfg(cfg, "rule34"))
    return _gelbooru_style(
        "https://api.rule34.xxx/index.php",
        md5,
        cfg,
        "rule34",
        extra,
        category_cache,
    )


def _lookup_gelbooru(
    md5: str, cfg: Dict, category_cache=None
) -> Optional[Dict]:
    extra = _auth_extra(_source_cfg(cfg, "gelbooru"))
    return _gelbooru_style(
        "https://gelbooru.com/index.php",
        md5,
        cfg,
        "gelbooru",
        extra,
        category_cache,
    )


def _lookup_danbooru(
    md5: str, cfg: Dict, category_cache=None
) -> Optional[Dict]:
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


def lookup(
    source: str, md5: str, cfg: Dict, category_cache=None
) -> Optional[Dict]:
    """Return {'tags': [(name, category)], 'safety': ...} or None if not found.

    `category_cache` (a booru_cache.TagCategoryCache, or any object exposing
    .get(source, names)/.put(source, mapping)) persists resolved tag
    categories; when omitted, a process-local cache is used.

    Raises BooruRetryError on transient failures and BooruError otherwise.
    """
    fn = _LOOKUPS.get(source)
    if not fn:
        raise BooruError("Unknown booru source: %r" % source)
    return fn(md5, cfg, category_cache)
