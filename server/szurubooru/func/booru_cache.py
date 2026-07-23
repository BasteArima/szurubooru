"""
Persistent tag -> category cache for booru hash imports.

booru.py stays free of any DB/ORM knowledge; the job runner and the single-post
endpoint hand it one of these caches to resolve tags against. A short-lived
in-memory layer sits in front of the `booru_tag_category` table so that, within
one job, a tag looked up once is never queried (from the network *or* the DB)
again, while the DB layer makes the resolution survive restarts and be shared
across jobs and single-post runs.
"""

from datetime import datetime
from typing import Dict, Iterable, List

from szurubooru import db, model


class TagCategoryCache:
    def __init__(self) -> None:
        self._mem = {}  # type: Dict[tuple, str]

    def get(self, source: str, names: Iterable[str]) -> Dict[str, str]:
        """Return the subset of `names` whose category is already known."""
        found = {}  # type: Dict[str, str]
        missing = []  # type: List[str]
        for name in names:
            cached = self._mem.get((source, name))
            if cached is not None:
                found[name] = cached
            else:
                missing.append(name)
        if missing:
            rows = (
                db.session.query(model.BooruTagCategory)
                .filter(
                    model.BooruTagCategory.source == source,
                    model.BooruTagCategory.name.in_(missing),
                )
                .all()
            )
            for row in rows:
                self._mem[(source, row.name)] = row.category
                found[row.name] = row.category
        return found

    def put(self, source: str, mapping: Dict[str, str]) -> None:
        """Persist newly-resolved tag -> category pairs (upsert)."""
        for name, category in mapping.items():
            if self._mem.get((source, name)) == category:
                continue
            self._mem[(source, name)] = category
            row = db.session.query(model.BooruTagCategory).get(
                (source, name)
            )
            if row is None:
                row = model.BooruTagCategory(source=source, name=name)
                db.session.add(row)
            row.category = category
            row.updated_time = datetime.utcnow()
