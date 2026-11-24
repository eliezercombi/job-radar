"""Keyword matching. Terms are case-insensitive and match on word boundaries,
so "go" does not fire on "google" and "react" does not fire on "reactive"."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache


@lru_cache(maxsize=512)
def _pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.strip().lower())
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.I)


def hits(text: str, terms) -> list[str]:
    return [term for term in terms if term.strip() and _pattern(term).search(text)]


@dataclass(frozen=True)
class Rule:
    include: tuple[str, ...] = ()      # at least one must match (empty = everything)
    exclude: tuple[str, ...] = ()      # none may match
    max_age_hours: float | None = None

    @classmethod
    def from_config(cls, config: dict) -> "Rule":
        return cls(
            include=tuple(config.get("include", [])),
            exclude=tuple(config.get("exclude", [])),
            max_age_hours=config.get("max_age_hours"),
        )

    def matched(self, post) -> list[str] | None:
        """Matching include terms, or None when the post is filtered out."""
        if self.max_age_hours is not None and post.age_hours > self.max_age_hours:
            return None
        haystack = f"{post.title}\n{post.text}"
        if hits(haystack, self.exclude):
            return None
        if not self.include:
            return []
        return hits(haystack, self.include) or None
