import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from radar.match import Rule, hits
from radar.sources import Post, first_line, parse_hn_comment, parse_remoteok, parse_telegram, strip_html
from radar.store import Store

TELEGRAM_PAGE = """
<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message" data-post="DevJobs/101">
<div class="tgme_widget_message_text js-message_text" dir="auto"><b>Contract: Telegram bot developer</b><br/>Budget $400 &amp; quick start<br/><br/>Write to @hr</div>
<div class="tgme_widget_message_footer"><time datetime="2026-11-20T10:00:00+00:00" class="time">10:00</time></div></div></div>
<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message" data-post="DevJobs/102">
<div class="tgme_widget_message_footer"><time datetime="2026-11-20T11:00:00+00:00" class="time">11:00</time></div></div></div>
"""


def post(text="Senior Go developer, remote contract", hours_ago=1.0, post_id="x:1"):
    return Post(post_id, "test", first_line(text), text, "https://example.org", datetime.now(timezone.utc) - timedelta(hours=hours_ago))


class Parsing(unittest.TestCase):
    def test_strip_html_keeps_paragraphs_and_entities(self):
        self.assertEqual(strip_html("A &amp; B<p>second  line</p><br>third"), "A & B\nsecond line\nthird")

    def test_first_line_truncates(self):
        self.assertEqual(len(first_line("x" * 300, limit=50)), 50)
        self.assertEqual(first_line("short\nsecond"), "short")

    def test_telegram_preview(self):
        posts = parse_telegram(TELEGRAM_PAGE)
        self.assertEqual(len(posts), 1, "the caption-less message is skipped")
        only = posts[0]
        self.assertEqual(only.id, "tg:devjobs/101")
        self.assertEqual(only.title, "Contract: Telegram bot developer")
        self.assertIn("Budget $400 & quick start", only.text)
        self.assertEqual(only.url, "https://t.me/DevJobs/101")
        self.assertEqual(only.posted_at, datetime(2026, 11, 20, 10, tzinfo=timezone.utc))

    def test_hn_comment(self):
        item = {"id": 7, "time": 1795000000, "text": "Acme | Remote | Contract<p>We build things."}
        parsed = parse_hn_comment(item)
        self.assertEqual(parsed.title, "Acme | Remote | Contract")
        self.assertEqual(parsed.url, "https://news.ycombinator.com/item?id=7")
        self.assertIsNone(parse_hn_comment({"id": 8, "time": 1, "text": "x", "dead": True}))
        self.assertIsNone(parse_hn_comment(None))

    def test_remoteok_skips_the_legal_notice(self):
        payload = [
            {"legal": "terms"},
            {"id": "55", "position": "Bot Developer", "company": "Acme", "tags": ["python", "telegram"],
             "description": "<p>Build bots</p>", "epoch": 1795000000, "url": "https://remoteok.com/remote-jobs/55"},
        ]
        posts = parse_remoteok(payload)
        self.assertEqual([p.title for p in posts], ["Bot Developer — Acme"])
        self.assertTrue(posts[0].text.startswith("python, telegram"))


class Matching(unittest.TestCase):
    def test_terms_match_whole_words_only(self):
        self.assertEqual(hits("We use Google Cloud and Django", ["go"]), [])
        self.assertEqual(hits("Go and Rust shop", ["go", "rust"]), ["go", "rust"])
        self.assertEqual(hits("C++ / Node.js", ["c++", "node.js"]), ["c++", "node.js"])

    def test_include_exclude_and_age(self):
        rule = Rule(include=("contract", "freelance"), exclude=("on-site",), max_age_hours=24)
        self.assertEqual(rule.matched(post()), ["contract"])
        self.assertIsNone(rule.matched(post("Full-time Go developer")))
        self.assertIsNone(rule.matched(post("Contract, on-site in Berlin")))
        self.assertIsNone(rule.matched(post(hours_ago=30)))

    def test_empty_include_matches_everything(self):
        self.assertEqual(Rule().matched(post("anything at all")), [])


class Storing(unittest.TestCase):
    def test_posts_are_reported_once(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(os.path.join(folder, "radar.db"))
            try:
                first, second = post(post_id="a:1"), post(post_id="a:2")
                self.assertEqual(store.unseen([first, second]), [first, second])
                store.remember([first])
                self.assertEqual(store.unseen([first, second]), [second])
                store.remember([first, second])
                self.assertEqual(store.unseen([first, second]), [])
                self.assertEqual(store.count(), 2)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
