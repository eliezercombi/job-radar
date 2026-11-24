"""Small HTTP helpers on top of urllib: timeouts, retries with backoff, one User-Agent."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

USER_AGENT = "job-radar/1.0 (+https://github.com/eliezercombi/job-radar)"
_MISSING = object()


def get_text(url: str, *, timeout: float = 20, retries: int = 2) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, "replace")
        except urllib.error.HTTPError as error:
            # A 4xx will not get better on a retry, except rate limiting.
            if error.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(1.5 * 2 ** attempt)
    raise AssertionError("unreachable")


def get_json(url: str, *, default=_MISSING, **kwargs):
    """Fetch and decode JSON. With ``default`` set, failures return it instead of raising."""
    try:
        return json.loads(get_text(url, **kwargs))
    except Exception:
        if default is _MISSING:
            raise
        return default


def post_json(url: str, payload: dict, *, timeout: float = 20) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())
