"""SQLite memory of what has already been reported."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    posted_at  TEXT NOT NULL,
    first_seen TEXT NOT NULL
)
"""


class Store:
    def __init__(self, path: str = "radar.db"):
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)
        self.db.commit()

    def unseen(self, posts: list) -> list:
        """Posts not reported before, in the order given."""
        known: set[str] = set()
        ids = [post.id for post in posts]
        for start in range(0, len(ids), 500):  # stay under SQLite's variable limit
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            known.update(row[0] for row in self.db.execute(f"SELECT id FROM seen WHERE id IN ({marks})", chunk))
        return [post for post in posts if post.id not in known]

    def remember(self, posts: list) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.db:
            self.db.executemany(
                "INSERT OR IGNORE INTO seen VALUES (?, ?, ?, ?, ?, ?)",
                [(p.id, p.source, p.title, p.url, p.posted_at.isoformat(timespec="seconds"), now) for p in posts],
            )

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]

    def close(self) -> None:
        self.db.close()
