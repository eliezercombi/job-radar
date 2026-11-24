"""Source adapters. Each one turns a public page or API into a list of Posts.

Parsing is kept in pure functions (``parse_*``) so it can be tested offline;
the ``fetch_*`` wrappers only add the network call.
"""

from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from .http import get_json, get_text


@dataclass(frozen=True)
class Post:
    id: str          # stable across runs, unique across sources
    source: str
    title: str
    text: str
    url: str
    posted_at: datetime

    @property
    def age_hours(self) -> float:
        return (datetime.now(timezone.utc) - self.posted_at).total_seconds() / 3600


_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"<br\s*/?>|</p>|<p>", re.I)
_SPACE = re.compile(r"[ \t\r\f\v]+")


def strip_html(fragment: str) -> str:
    """Markup to plain text, keeping paragraph breaks."""
    text = _TAG.sub("", _BREAK.sub("\n", fragment or ""))
    lines = (_SPACE.sub(" ", line).strip() for line in html.unescape(text).split("\n"))
    return "\n".join(line for line in lines if line)


def first_line(text: str, limit: int = 110) -> str:
    line = text.split("\n", 1)[0]
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# Telegram public channels (https://t.me/s/<channel>)
# --------------------------------------------------------------------------- #

_TG_MESSAGE = re.compile(r'<div class="tgme_widget_message_wrap')
_TG_ID = re.compile(r'data-post="([^"]+)"')
_TG_TIME = re.compile(r'<time datetime="([^"]+)"')
_TG_TEXT = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>\s*(?:<div class="tgme_widget_message_|<a class="tgme_widget_message_|</div>)', re.S)


def parse_telegram(page: str) -> list[Post]:
    posts = []
    for block in _TG_MESSAGE.split(page)[1:]:
        post_id, stamp, body = _TG_ID.search(block), _TG_TIME.search(block), _TG_TEXT.search(block)
        if not (post_id and stamp and body):
            continue  # service messages, media without a caption
        text = strip_html(body.group(1))
        if not text:
            continue
        posts.append(Post(
            id=f"tg:{post_id.group(1).lower()}",
            source=f"t.me/{post_id.group(1).split('/')[0]}",
            title=first_line(text),
            text=text,
            url=f"https://t.me/{post_id.group(1)}",
            posted_at=datetime.fromisoformat(stamp.group(1)),
        ))
    return posts


def fetch_telegram(channel: str) -> list[Post]:
    return parse_telegram(get_text(f"https://t.me/s/{channel.lstrip('@')}"))


# --------------------------------------------------------------------------- #
# Hacker News "Who is hiring?" (official Firebase API)
# --------------------------------------------------------------------------- #

HN = "https://hacker-news.firebaseio.com/v0"


def parse_hn_comment(item: dict | None) -> Post | None:
    if not item or item.get("dead") or item.get("deleted") or not item.get("text"):
        return None
    text = strip_html(item["text"])
    return Post(
        id=f"hn:{item['id']}",
        source="news.ycombinator.com",
        title=first_line(text),
        text=text,
        url=f"https://news.ycombinator.com/item?id={item['id']}",
        posted_at=datetime.fromtimestamp(item["time"], timezone.utc),
    )


def fetch_hn_hiring(limit: int = 400, workers: int = 16) -> list[Post]:
    """Top-level comments of the newest "Who is hiring?" thread."""
    submitted = get_json(f"{HN}/user/whoishiring.json")["submitted"][:8]
    thread = next(
        (story for story in (get_json(f"{HN}/item/{i}.json") for i in submitted)
         if story and "who is hiring" in story.get("title", "").lower()),
        None,
    )
    if not thread:
        return []
    kids = thread.get("kids", [])[:limit]
    with ThreadPoolExecutor(workers) as pool:
        items = pool.map(lambda kid: get_json(f"{HN}/item/{kid}.json", default=None), kids)
        return [post for post in map(parse_hn_comment, items) if post]


# --------------------------------------------------------------------------- #
# RemoteOK (public JSON feed)
# --------------------------------------------------------------------------- #

def parse_remoteok(payload: list) -> list[Post]:
    posts = []
    for job in payload:
        if not isinstance(job, dict) or "id" not in job or "position" not in job:
            continue  # the first element is a legal notice, not a job
        company = job.get("company") or "Unknown"
        tags = ", ".join(job.get("tags") or [])
        posts.append(Post(
            id=f"remoteok:{job['id']}",
            source="remoteok.com",
            title=f"{job['position']} — {company}",
            text="\n".join(part for part in (tags, strip_html(job.get("description", ""))) if part),
            url=job.get("url") or f"https://remoteok.com/remote-jobs/{job['id']}",
            posted_at=datetime.fromtimestamp(int(job.get("epoch", 0)), timezone.utc),
        ))
    return posts


def fetch_remoteok() -> list[Post]:
    return parse_remoteok(get_json("https://remoteok.com/api"))


# --------------------------------------------------------------------------- #

def build(spec: dict):
    """Turn one entry of the config's ``sources`` list into a zero-argument fetcher."""
    kind = spec.get("type")
    if kind == "telegram":
        return lambda: fetch_telegram(spec["channel"])
    if kind == "hn_hiring":
        return lambda: fetch_hn_hiring(limit=int(spec.get("limit", 400)))
    if kind == "remoteok":
        return fetch_remoteok
    raise ValueError(f"Unknown source type: {kind!r}")


def label(spec: dict) -> str:
    return f"telegram:{spec['channel']}" if spec.get("type") == "telegram" else str(spec.get("type"))


__all__ = ["Post", "build", "label", "parse_telegram", "parse_hn_comment", "parse_remoteok", "strip_html", "first_line"]
