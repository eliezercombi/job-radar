# job-radar

Watches public job feeds, keeps the posts that match your keywords, and tells you about each one once. Output goes to the terminal, a CSV or JSON file, or a Telegram chat.

Python 3.10+, standard library only. Nothing to install.

```text
$ python -m radar --config config.json
 24h  remoteok.com            Renewals Manager - LATAM — GitLab  [contract]
      https://remoteok.com/remote-jobs/remote-renewals-manager-latam-gitlab-1138065
  3d  remoteok.com            Part-Time Temporary HR Business Partner — Elation Health  [part-time]
      https://remoteok.com/remote-jobs/remote-part-time-temporary-hr-business-partner-...

379 posts scanned, 8 matched, 8 new
```

Run it again and only posts that appeared since the last run are shown.

## Use

```bash
cp config.example.json config.json    # then edit keywords and sources
python -m radar                       # new matches only
python -m radar --all                 # every current match
python -m radar --csv out.csv --json out.json
python -m radar --dry-run             # look without marking anything as seen
```

To get matches in Telegram, set two environment variables and schedule the command with cron or Task Scheduler:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
export TELEGRAM_CHAT_ID=123456789
python -m radar
```

## Config

```json
{
  "sources": [
    { "type": "hn_hiring", "limit": 400 },
    { "type": "remoteok" },
    { "type": "telegram", "channel": "cryptojobslist" }
  ],
  "include": ["contract", "freelance", "telegram bot"],
  "exclude": ["on-site", "relocation"],
  "max_age_hours": 72
}
```

| Key | Meaning |
| --- | --- |
| `sources` | Where to look. `hn_hiring` reads the current "Who is hiring?" thread through the official Hacker News API, `remoteok` reads the public JSON feed, `telegram` reads the public web preview of a channel. |
| `include` | A post must contain at least one of these. Leave empty to keep everything. |
| `exclude` | A post containing any of these is dropped. |
| `max_age_hours` | Ignore posts older than this. |

Keywords match whole words, case-insensitively: `go` does not fire on "Google", and terms such as `c++` or `node.js` work as written.

## How it behaves

- Sources are fetched in parallel. If one fails, the others still report and the failure is printed as a warning.
- Requests have timeouts and retry with backoff on rate limits and server errors.
- Seen posts are stored in a local SQLite file (`radar.db`), so de-duplication survives restarts.
- A first run sends at most 20 Telegram messages, so it cannot flood a chat.
- It only reads pages and APIs that are public without logging in. Check each site's terms before adding it at a higher frequency.

## Adding a source

A source is a function that returns a list of `Post` objects. Write a pure `parse_*` function for the page or payload, wrap it in a `fetch_*` function, and add a branch in `sources.build`. The parsers are tested offline in `tests/`.

```bash
python -m unittest discover -s tests
```

## Licence

MIT
