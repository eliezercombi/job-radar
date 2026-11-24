"""Command line entry point: ``python -m radar --config config.json``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from . import notify, sources
from .match import Rule
from .store import Store


def collect(specs: list[dict]) -> tuple[list, list[str]]:
    """Fetch every source in parallel. One broken source never sinks the run."""
    posts, problems = [], []

    def run(spec):
        try:
            return sources.build(spec)(), None
        except Exception as error:  # noqa: BLE001 - report it and carry on
            return [], f"{sources.label(spec)}: {type(error).__name__}: {error}"

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(specs)))) as pool:
        for found, problem in pool.map(run, specs):
            posts.extend(found)
            if problem:
                problems.append(problem)
    return posts, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Report new job posts that match your keywords.")
    parser.add_argument("--config", default="config.json", help="path to the config file (default: config.json)")
    parser.add_argument("--db", default="radar.db", help="SQLite file remembering what was already reported")
    parser.add_argument("--all", action="store_true", help="show every match, not only the unseen ones")
    parser.add_argument("--dry-run", action="store_true", help="do not mark results as seen and do not notify")
    parser.add_argument("--csv", metavar="FILE", help="also write the results to a CSV file")
    parser.add_argument("--json", metavar="FILE", help="also write the results to a JSON file")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    with open(args.config, encoding="utf-8") as handle:
        config = json.load(handle)
    rule = Rule.from_config(config)

    posts, problems = collect(config["sources"])
    matched = [(post, terms) for post in posts if (terms := rule.matched(post)) is not None]
    matched.sort(key=lambda row: row[0].posted_at, reverse=True)

    store = Store(args.db)
    try:
        fresh = {post.id for post in store.unseen([post for post, _ in matched])}
        rows = matched if args.all else [row for row in matched if row[0].id in fresh]

        notify.table(rows)
        if args.csv:
            notify.to_csv(rows, args.csv)
        if args.json:
            notify.to_json(rows, args.json)

        sent = 0
        if not args.dry_run:
            token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
            if token and chat:
                sent = notify.telegram([row for row in rows if row[0].id in fresh], token, chat)
            store.remember([post for post, _ in matched])

        summary = f"{len(posts)} posts scanned, {len(matched)} matched, {len(fresh)} new"
        print(f"\n{summary}{f', {sent} sent to Telegram' if sent else ''}", file=sys.stderr)
        for problem in problems:
            print(f"warning: {problem}", file=sys.stderr)
    finally:
        store.close()
    return 1 if problems and not posts else 0


if __name__ == "__main__":
    raise SystemExit(main())
