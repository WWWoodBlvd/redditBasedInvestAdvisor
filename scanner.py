"""
Async Reddit scanner — fires all subreddit requests simultaneously.
Uses aiohttp for non-blocking I/O with a shared connection pool.

Supports two modes:
  - Public JSON  (no credentials)         → works on residential IPs
  - OAuth        (CLIENT_ID + SECRET set) → works everywhere, incl. cloud IPs
"""

import asyncio
import aiohttp
import os
import time
from datetime import datetime, timezone
from typing import Optional, Callable

HEADERS = {
    "User-Agent": "web:redditBasedInvestAdvisor:v1.1 (by /u/WWWoodBlvd)",
    "Accept": "application/json",
}

SEMAPHORE_LIMIT = 20
MAX_RETRIES = 3

SCAN_LIMITS = {
    "Turbo  ⚡ (25 posts, titles only  — ~3 sec)":  {"posts": 25,  "comments": 0},
    "Quick  🔍 (100 posts, titles only — ~10 sec)": {"posts": 100, "comments": 0},
    "Deep   🔬 (200 posts + comments  — ~30 sec)":  {"posts": 200, "comments": 10},
}

# ── OAuth support ───────────────────────────────────────────────────────────
_CLIENT_ID:     Optional[str] = os.environ.get("REDDIT_CLIENT_ID")
_CLIENT_SECRET: Optional[str] = os.environ.get("REDDIT_CLIENT_SECRET")
_token:         Optional[str] = None
_token_expires: float = 0.0


def configure_oauth(client_id: str, client_secret: str):
    """Inject credentials at runtime — called from app.py reading Streamlit secrets."""
    global _CLIENT_ID, _CLIENT_SECRET
    if client_id and client_secret:
        _CLIENT_ID = client_id
        _CLIENT_SECRET = client_secret


def _use_oauth() -> bool:
    return bool(_CLIENT_ID and _CLIENT_SECRET)


def _api_host() -> str:
    return "https://oauth.reddit.com" if _use_oauth() else "https://www.reddit.com"


async def _get_token(session: aiohttp.ClientSession) -> Optional[str]:
    global _token, _token_expires
    if _token and time.time() < _token_expires - 30:
        return _token
    if not _use_oauth():
        return None

    try:
        async with session.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=aiohttp.BasicAuth(_CLIENT_ID, _CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status == 200:
                payload = await r.json()
                _token = payload.get("access_token")
                _token_expires = time.time() + payload.get("expires_in", 3600)
                return _token
    except Exception:
        return None
    return None


# ── Low-level fetch ──────────────────────────────────────────────────────────

async def _get(session: aiohttp.ClientSession, sem: asyncio.Semaphore, url: str, params: dict) -> Optional[dict]:
    """Retry on rate-limit / transient errors with exponential backoff."""
    auth_header = {}
    if _use_oauth():
        token = await _get_token(session)
        if token:
            auth_header = {"Authorization": f"bearer {token}"}

    async with sem:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(
                    url, params=params, headers=auth_header,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status == 200:
                        return await r.json(content_type=None)
                    if r.status in (429, 503):
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if r.status in (401, 403, 404):
                        return None   # don't retry
            except (asyncio.TimeoutError, aiohttp.ClientError):
                await asyncio.sleep(1 + attempt)
    return None


# ── Post fetching ────────────────────────────────────────────────────────────

async def _fetch_listing_page(session, sem, subreddit, after, limit):
    params = {"limit": limit, "raw_json": 1}
    if after:
        params["after"] = after
    return await _get(session, sem, f"{_api_host()}/r/{subreddit}/new", params) \
        if _use_oauth() else \
        await _get(session, sem, f"{_api_host()}/r/{subreddit}/new.json", params)


async def _fetch_posts(session, sem, subreddit: str, days: int, max_posts: int) -> list:
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    posts = []
    after = None
    pages_needed = max(1, (max_posts + 99) // 100)

    for _ in range(pages_needed):
        data = await _fetch_listing_page(session, sem, subreddit, after, min(100, max_posts - len(posts)))
        if not data or "data" not in data:
            break

        children = data["data"].get("children", [])
        if not children:
            break

        for child in children:
            p = child.get("data", {})
            if p.get("created_utc", 0) < cutoff:
                return posts
            posts.append(p)

        after = data["data"].get("after")
        if not after:
            break

    return posts


# ── Comment fetching ─────────────────────────────────────────────────────────

async def _fetch_comments(session, sem, subreddit: str, post_id: str) -> list:
    """Returns list of {body, author} dicts for top-level comments."""
    suffix = "" if _use_oauth() else ".json"
    url = f"{_api_host()}/r/{subreddit}/comments/{post_id}{suffix}"
    data = await _get(session, sem, url, {"raw_json": 1, "limit": 50, "depth": 1})
    if not data or len(data) < 2:
        return []
    out = []
    for c in data[1]["data"].get("children", []):
        body = c.get("data", {}).get("body", "")
        if body and body not in ("[deleted]", "[removed]"):
            out.append({
                "body":   body,
                "author": c.get("data", {}).get("author", "[anonymous]"),
            })
    return out


# ── Per-subreddit scan ───────────────────────────────────────────────────────

async def _scan_one(session, sem, subreddit, days, max_posts, max_comments) -> list:
    posts = await _fetch_posts(session, sem, subreddit, days, max_posts)
    items = []

    for p in posts:
        text = f"{p.get('title', '')} {p.get('selftext', '')}".strip()
        if text:
            items.append({
                "subreddit":   subreddit,
                "text":        text,
                "created_utc": p.get("created_utc", 0),
                "post_id":     p.get("id", ""),
                "author":      p.get("author", "[anonymous]"),
                "score":       p.get("score", 0),
            })

    if max_comments > 0 and posts:
        top_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)[:max_comments]
        comment_tasks = [_fetch_comments(session, sem, subreddit, p["id"]) for p in top_posts]
        results = await asyncio.gather(*comment_tasks)
        for p, comments in zip(top_posts, results):
            for c in comments:
                items.append({
                    "subreddit":   subreddit,
                    "text":        c["body"],
                    "created_utc": p.get("created_utc", 0),
                    "post_id":     p.get("id", ""),
                    "author":      c["author"],
                    "score":       p.get("score", 0),
                })

    return items


# ── Main entry point ─────────────────────────────────────────────────────────

async def _scan_one_named(session, sem, sub, days, max_posts, max_comments):
    items = await _scan_one(session, sem, sub, days, max_posts, max_comments)
    return sub, items


async def _scan_all_async(subreddits, days, max_posts, max_comments, on_progress) -> list:
    sem = asyncio.Semaphore(SEMAPHORE_LIMIT)
    connector = aiohttp.TCPConnector(limit=30)
    all_items = []
    total = len(subreddits)
    done = 0
    start = time.time()

    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        tasks = [
            asyncio.create_task(_scan_one_named(session, sem, sub, days, max_posts, max_comments))
            for sub in subreddits
        ]
        for coro in asyncio.as_completed(tasks):
            try:
                subreddit, items = await coro
            except Exception:
                subreddit, items = "unknown", []
            all_items.extend(items)
            done += 1
            elapsed = time.time() - start
            on_progress(subreddit, len(items), elapsed, done, total)

    return all_items


def scan_all(subreddits, days, max_posts, max_comments, on_progress):
    """Sync wrapper — runs the async engine from Streamlit."""
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(
            _scan_all_async(subreddits, days, max_posts, max_comments, on_progress)
        )
    finally:
        loop.close()


def auth_mode() -> str:
    return "OAuth (authenticated)" if _use_oauth() else "Public JSON (anonymous)"
