"""Delivery: terminal table, CSV/JSON export and Telegram messages."""

from __future__ import annotations

import csv
import html
import json
import sys

from .http import post_json


def age(hours: float) -> str:
    if hours < 1:
        return f"{hours * 60:.0f}m"
    return f"{hours:.0f}h" if hours < 48 else f"{hours / 24:.0f}d"


def table(rows: list[tuple], out=None) -> None:
    out = out or sys.stdout
    for post, terms in rows:
        tags = f"  [{', '.join(terms)}]" if terms else ""
        out.write(f"{age(post.age_hours):>4}  {post.source:<22.22}  {post.title}{tags}\n      {post.url}\n")


def to_csv(rows: list[tuple], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:  # BOM so Excel opens it cleanly
        writer = csv.writer(handle)
        writer.writerow(["posted_at", "source", "title", "matched", "url"])
        for post, terms in rows:
            writer.writerow([post.posted_at.isoformat(timespec="minutes"), post.source, post.title, "; ".join(terms), post.url])


def to_json(rows: list[tuple], path: str) -> None:
    payload = [
        {"id": p.id, "source": p.source, "title": p.title, "url": p.url,
         "posted_at": p.posted_at.isoformat(timespec="seconds"), "matched": terms, "text": p.text}
        for p, terms in rows
    ]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def telegram(rows: list[tuple], token: str, chat_id: str, limit: int = 20) -> int:
    """One message per post, capped so a first run cannot flood the chat. Returns how many were sent."""
    sent = 0
    for post, terms in rows[:limit]:
        text = (
            f"<b>{html.escape(post.title)}</b>\n"
            f"{html.escape(post.source)} · {age(post.age_hours)} ago"
            + (f" · {html.escape(', '.join(terms))}" if terms else "")
            + f"\n{html.escape(post.url)}"
        )
        post_json(
            f"https://api.telegram.org/bot{token}/sendMessage",
            {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        )
        sent += 1
    return sent
