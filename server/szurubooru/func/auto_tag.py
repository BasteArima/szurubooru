"""
Core auto-tagging logic: apply type tags, look up tags by MD5 on boorus, and
record per-post-per-method processing state. Shared by the single-post API
endpoint and the background job runner.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from szurubooru import config, db, model
from szurubooru.func import (
    auto_tag_config,
    booru,
    booru_cache,
    posts,
    tags,
    versions,
)

logger = logging.getLogger(__name__)

METHODS = (
    model.PostAutoTag.METHOD_TYPE_TAGS,
    model.PostAutoTag.METHOD_HASH,
    model.PostAutoTag.METHOD_AI,
)


def _tag_name_regex():
    return re.compile(config.config["tag_name_regex"])


def _normalize(name: str) -> Optional[str]:
    name = (name or "").strip().replace(" ", "_")
    if not name:
        return None
    try:
        if not _tag_name_regex().match(name):
            return None
    except re.error:
        pass
    return name


def _tag_display_name(tag: model.Tag) -> Optional[str]:
    """A tag's name read from the in-memory `names` relationship. Needed because
    `Tag.first_name` is a deferred SQL column_property that stays None until the
    tag is flushed, so it is unusable on the freshly-created tags returned by
    update_post_tags (reading it there raised AttributeError on None)."""
    if getattr(tag, "names", None):
        return tag.names[0].name
    return tag.first_name


def _apply_tags(post: model.Post, pairs: List[Tuple[str, str]]) -> int:
    """Add missing tags (with szuru category) to the post; returns count added.

    Only newly-created tags get their category set; existing tags keep theirs
    so a manual categorisation is never overwritten.
    """
    current = set()
    for tag in post.tags:
        for tag_name in tag.names:
            current.add(tag_name.name.lower())

    to_add = []  # type: List[Tuple[str, str]]
    seen = set()
    for name, category in pairs:
        normalized = _normalize(name)
        if not normalized:
            continue
        low = normalized.lower()
        if low in current or low in seen:
            continue
        seen.add(low)
        to_add.append((normalized, category))

    if not to_add:
        return 0

    current_names = [
        name for name in map(_tag_display_name, post.tags) if name
    ]
    new_tags = posts.update_post_tags(
        post, current_names + [name for name, _ in to_add]
    )
    category_by_name = {name.lower(): category for name, category in to_add}
    for tag in new_tags:
        name = _tag_display_name(tag)
        if not name:
            continue
        category = category_by_name.get(name.lower())
        if category:
            try:
                tags.update_tag_category_name(tag, category)
            except Exception as ex:  # unknown category -> keep default
                logger.warning("auto-tag category %r: %s", category, ex)
    return len(to_add)


def _maybe_apply_safety(
    post: model.Post, safety: Optional[str], hash_cfg: Dict
) -> bool:
    if not safety or not hash_cfg.get("applySafety"):
        return False
    if (
        hash_cfg.get("safetyOnlyIfUnset")
        and post.safety != model.Post.SAFETY_SAFE
    ):
        return False
    if safety not in ("safe", "sketchy", "unsafe"):
        return False
    posts.update_post_safety(post, safety)
    return True


def apply_type_tags(
    post: model.Post, cfg: Dict
) -> Tuple[str, int]:
    type_cfg = cfg["typeTags"]
    if not type_cfg.get("enabled"):
        return (model.PostAutoTag.STATUS_DONE, 0)
    category = type_cfg.get("tagCategory") or "meta"
    is_video = post.type == model.Post.TYPE_VIDEO
    is_animated = post.type in (
        model.Post.TYPE_VIDEO,
        model.Post.TYPE_ANIMATION,
    )
    pairs = []  # type: List[Tuple[str, str]]
    if is_video and type_cfg.get("videoTag"):
        pairs.append((type_cfg["videoTag"], category))
    if is_animated and type_cfg.get("animatedTag"):
        pairs.append((type_cfg["animatedTag"], category))
    added = _apply_tags(post, pairs)
    return (model.PostAutoTag.STATUS_DONE, added)


def apply_type_tags_on_upload(post: model.Post) -> None:
    """Best-effort type tagging during upload (never blocks the upload)."""
    try:
        cfg = auto_tag_config.get_config()
        type_cfg = cfg["typeTags"]
        if not type_cfg.get("enabled") or not type_cfg.get("applyOnUpload"):
            return
        apply_type_tags(post, cfg)
    except Exception as ex:  # noqa: BLE001
        logger.warning("type-tag on upload failed: %s", ex)


def apply_hash(
    post: model.Post, cfg: Dict, category_cache=None
) -> Tuple[str, Optional[str], int]:
    hash_cfg = cfg["hash"]
    if not hash_cfg.get("enabled"):
        return (model.PostAutoTag.STATUS_DONE, None, 0)
    md5 = post.checksum_md5
    if not md5:
        return (model.PostAutoTag.STATUS_EMPTY, None, 0)

    sources_cfg = hash_cfg.get("sources", {})
    ordered_sources = sorted(
        (
            name
            for name, opts in sources_cfg.items()
            if isinstance(opts, dict) and opts.get("enabled")
        ),
        key=lambda name: sources_cfg[name].get("priority", 99),
    )

    had_retryable = False
    for source in ordered_sources:
        try:
            result = booru.lookup(source, md5, hash_cfg, category_cache)
        except booru.BooruRetryError as ex:
            had_retryable = True
            logger.warning("auto-tag hash %s: %s", source, ex)
            continue
        except booru.BooruError as ex:
            logger.warning("auto-tag hash %s: %s", source, ex)
            continue
        if result:
            category_map = hash_cfg.get("categoryMap", {})
            pairs = [
                (name, category_map.get(canon, canon) or "general")
                for name, canon in result["tags"]
            ]
            added = _apply_tags(post, pairs)
            _maybe_apply_safety(post, result.get("safety"), hash_cfg)
            return (model.PostAutoTag.STATUS_DONE, source, added)

    if had_retryable:
        return (model.PostAutoTag.STATUS_ERROR, None, 0)
    return (model.PostAutoTag.STATUS_EMPTY, None, 0)


def _record(
    post_id: int,
    method: str,
    status: str,
    source: Optional[str],
    added: int,
    message: Optional[str],
) -> None:
    row = db.session.query(model.PostAutoTag).get((post_id, method))
    if not row:
        row = model.PostAutoTag(post_id=post_id, method=method)
        db.session.add(row)
    row.status = status
    row.source = source
    row.added_count = added or 0
    row.message = (message or "")[:500] or None
    row.attempt_time = datetime.utcnow()


def get_state(post_id: int) -> Dict[str, model.PostAutoTag]:
    rows = (
        db.session.query(model.PostAutoTag)
        .filter(model.PostAutoTag.post_id == post_id)
        .all()
    )
    return {row.method: row for row in rows}


def should_run_methods(
    post_id: int,
    methods: List[str],
    mode: str,
    retry_empty: bool,
) -> List[str]:
    if mode == "all":
        return list(methods)
    states = get_state(post_id)
    result = []
    for method in methods:
        row = states.get(method)
        if row is None:
            if mode == "new":
                result.append(method)
        elif row.status == model.PostAutoTag.STATUS_ERROR:
            result.append(method)
        elif (
            row.status == model.PostAutoTag.STATUS_EMPTY
            and method == model.PostAutoTag.METHOD_HASH
            and retry_empty
            and mode == "new"
        ):
            result.append(method)
    return result


def run_methods_on_post(
    post: model.Post, methods: List[str], cfg: Dict, category_cache=None
) -> Dict[str, Dict]:
    """Run the given methods on a post, record state, commit. Returns a summary
    per method: {method: {status, added, message}}.

    `category_cache` is reused across posts by the job runner so a backfill
    resolves each unique booru tag once; a fresh DB-backed cache is created
    when omitted (single-post runs still benefit from a job's cached tags).
    """
    if category_cache is None:
        category_cache = booru_cache.TagCategoryCache()
    results = {}  # type: Dict[str, Dict]
    changed = False
    for method in methods:
        status = model.PostAutoTag.STATUS_ERROR
        source = None
        added = 0
        message = None
        try:
            if method == model.PostAutoTag.METHOD_TYPE_TAGS:
                status, added = apply_type_tags(post, cfg)
            elif method == model.PostAutoTag.METHOD_HASH:
                status, source, added = apply_hash(post, cfg, category_cache)
            elif method == model.PostAutoTag.METHOD_AI:
                # Delivery B: AI tagger microservice not wired yet
                status, added = (
                    model.PostAutoTag.STATUS_ERROR,
                    0,
                )
                message = "AI tagger not implemented yet"
            else:
                continue
        except Exception as ex:  # noqa: BLE001 - record and keep going
            logger.exception(ex)
            status, added, message = (
                model.PostAutoTag.STATUS_ERROR,
                0,
                str(ex),
            )
        if added:
            changed = True
        _record(post.post_id, method, status, source, added, message)
        results[method] = {
            "status": status,
            "added": added,
            "source": source,
            "message": message,
        }

    if changed:
        post.last_edit_time = datetime.utcnow()
        versions.bump_version(post)
    db.session.commit()
    return results


def serialize_post_state(post_id: int) -> List[Dict]:
    """Auto-tag history for the post page."""
    state = get_state(post_id)
    ret = []
    for method in METHODS:
        row = state.get(method)
        ret.append(
            {
                "method": method,
                "status": row.status if row else None,
                "source": row.source if row else None,
                "addedCount": row.added_count if row else None,
                "time": row.attempt_time if row else None,
                "message": row.message if row else None,
            }
        )
    return ret
