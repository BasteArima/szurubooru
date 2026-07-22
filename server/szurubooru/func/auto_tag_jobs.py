"""
In-process background job runner for bulk auto-tagging.

One job at a time. The job runs in a daemon thread with its own (thread-local)
DB session. Progress is written with targeted UPDATEs that never touch the
`status` column, while pause/cancel are signalled by the API writing `status`
(paused / cancelling) which the thread polls with a fresh read each iteration.
A job left active by a container restart is marked `interrupted` on startup and
can simply be re-run (per-post-per-method state makes it resumable).
"""

import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from szurubooru import db, errors, model
from szurubooru.func import auto_tag, auto_tag_config

logger = logging.getLogger(__name__)

_start_lock = threading.Lock()

Job = model.AutoTagJob


def serialize_job(job: Optional[model.AutoTagJob]) -> Optional[Dict]:
    if not job:
        return None
    try:
        methods = json.loads(job.methods or "[]")
    except ValueError:
        methods = []
    return {
        "id": job.job_id,
        "status": job.status,
        "methods": methods,
        "selectionMode": job.selection_mode,
        "retryEmpty": job.retry_empty,
        "scopeQuery": job.scope_query,
        "total": job.total,
        "processed": job.processed,
        "tagged": job.tagged,
        "failed": job.failed,
        "errors": job.errors,
        "currentPostId": job.current_post_id,
        "message": job.message,
        "startedAt": job.started_at,
        "updatedAt": job.updated_at,
        "finishedAt": job.finished_at,
    }


def get_current_job() -> Optional[model.AutoTagJob]:
    return (
        db.session.query(Job).order_by(Job.job_id.desc()).first()
    )


def _get_active_job() -> Optional[model.AutoTagJob]:
    return (
        db.session.query(Job)
        .filter(Job.status.in_(Job.ACTIVE_STATUSES))
        .order_by(Job.job_id.desc())
        .first()
    )


def mark_interrupted_jobs() -> None:
    """Called at startup: any job the previous process left running is dead."""
    db.session.query(Job).filter(Job.status.in_(Job.ACTIVE_STATUSES)).update(
        {"status": Job.STATUS_INTERRUPTED, "finished_at": datetime.utcnow()},
        synchronize_session=False,
    )
    db.session.commit()


def _read_status(job_id: int) -> Optional[str]:
    return (
        db.session.query(Job.status).filter(Job.job_id == job_id).scalar()
    )


def _update_progress(job_id: int, **fields) -> None:
    fields["updated_at"] = datetime.utcnow()
    db.session.query(Job).filter(Job.job_id == job_id).update(
        fields, synchronize_session=False
    )
    db.session.commit()


def _set_status(job_id: int, status: str, message: Optional[str] = None) -> None:
    values = {"status": status, "updated_at": datetime.utcnow()}
    if status in (
        Job.STATUS_COMPLETED,
        Job.STATUS_CANCELLED,
        Job.STATUS_ERROR,
        Job.STATUS_INTERRUPTED,
    ):
        values["finished_at"] = datetime.utcnow()
    if message is not None:
        values["message"] = message[:500]
    db.session.query(Job).filter(Job.job_id == job_id).update(
        values, synchronize_session=False
    )
    db.session.commit()


def _candidate_post_ids(query: str) -> List[int]:
    query = (query or "").strip()
    if not query:
        rows = (
            db.session.query(model.Post.post_id)
            .order_by(model.Post.post_id.asc())
            .all()
        )
        return [row[0] for row in rows]

    from szurubooru import search

    executor = search.Executor(search.configs.PostSearchConfig())
    executor.config.user = None  # admin job: no safety filtering
    ids = []  # type: List[int]
    offset = 0
    while True:
        count, entities = executor.execute(query, offset, 100)
        if not entities:
            break
        ids.extend(entity.post_id for entity in entities)
        offset += len(entities)
        if offset >= count:
            break
    return ids


def _run_job(
    job_id: int,
    methods: List[str],
    mode: str,
    retry_empty: bool,
    query: str,
    cfg: Dict,
) -> None:
    try:
        ids = _candidate_post_ids(query)
        _update_progress(job_id, total=len(ids))

        processed = tagged = failed = errors = 0
        for post_id in ids:
            control = _read_status(job_id)
            if control == Job.STATUS_CANCELLING:
                _set_status(job_id, Job.STATUS_CANCELLED)
                return
            while control == Job.STATUS_PAUSED:
                time.sleep(1.0)
                control = _read_status(job_id)
                if control == Job.STATUS_CANCELLING:
                    _set_status(job_id, Job.STATUS_CANCELLED)
                    return

            post = db.session.query(model.Post).get(post_id)
            if post is not None:
                run_methods = auto_tag.should_run_methods(
                    post_id, methods, mode, retry_empty
                )
                if run_methods:
                    results = auto_tag.run_methods_on_post(
                        post, run_methods, cfg
                    )
                    if any(r["added"] for r in results.values()):
                        tagged += 1
                    if any(
                        r["status"] == model.PostAutoTag.STATUS_ERROR
                        for r in results.values()
                    ):
                        errors += 1

            processed += 1
            _update_progress(
                job_id,
                processed=processed,
                tagged=tagged,
                failed=failed,
                errors=errors,
                current_post_id=post_id,
            )
            db.session.expunge_all()

        _set_status(job_id, Job.STATUS_COMPLETED)
    except Exception as ex:  # noqa: BLE001
        logger.exception(ex)
        try:
            _set_status(job_id, Job.STATUS_ERROR, message=str(ex))
        except Exception:
            pass
    finally:
        db.session.remove()


def start_job(
    methods: List[str], mode: str, retry_empty: bool, query: str
) -> Dict:
    methods = [m for m in (methods or []) if m in auto_tag.METHODS]
    if not methods:
        raise errors.ValidationError("No valid auto-tag methods selected.")
    if mode not in ("new", "errors", "all"):
        mode = "new"

    with _start_lock:
        if _get_active_job():
            raise errors.IntegrityError(
                "An auto-tag job is already running."
            )
        cfg = auto_tag_config.get_config()
        job = Job()
        job.status = Job.STATUS_RUNNING
        job.methods = json.dumps(methods)
        job.selection_mode = mode
        job.retry_empty = bool(retry_empty)
        job.scope_query = query or ""
        job.started_at = datetime.utcnow()
        job.updated_at = job.started_at
        db.session.add(job)
        db.session.commit()
        job_id = job.job_id

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, methods, mode, bool(retry_empty), query or "", cfg),
        daemon=True,
    )
    thread.start()
    return serialize_job(db.session.query(Job).get(job_id))


def pause_job() -> Dict:
    job = _get_active_job()
    if not job:
        raise errors.NotFoundError("No running auto-tag job.")
    if job.status == Job.STATUS_RUNNING:
        _set_status(job.job_id, Job.STATUS_PAUSED)
    return serialize_job(db.session.query(Job).get(job.job_id))


def resume_job() -> Dict:
    job = _get_active_job()
    if not job:
        raise errors.NotFoundError("No paused auto-tag job.")
    if job.status == Job.STATUS_PAUSED:
        _set_status(job.job_id, Job.STATUS_RUNNING)
    return serialize_job(db.session.query(Job).get(job.job_id))


def cancel_job() -> Dict:
    job = _get_active_job()
    if not job:
        raise errors.NotFoundError("No running auto-tag job.")
    _set_status(job.job_id, Job.STATUS_CANCELLING)
    return serialize_job(db.session.query(Job).get(job.job_id))
