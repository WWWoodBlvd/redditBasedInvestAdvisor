"""
Async Reddit scanner — fires all subreddit requests simultaneously.
Uses aiohttp for non-blocking I/O with a shared connection pool.
"""

import asyncio
import aiohttp
import time
from datetime import datetime, timezone
from typing import Optional, Callable

# Reddit's recommended UA format: <platform>:<app-id>:<version> (by /u/<username>)
# Generic UAs get globally rate-limited, especially from cloud IPs.
HEADERS = {
    "User-Agent": "web:redditBasedInvestAdvisor:v1.1 (by /u/WWWoodBlvd)",
    "Accept": "application/json",
}

# Limit concurrent requests to stay within Reddit's rate limit (~60/min)
SEMAPHORE_LIMIT = 20
MAX_RETRIES = 3

SCAN_LIMITS = {
    "Turbo  ⚡ (25 posts, titles only  — ~3 sec)":  {"posts": 25,  "comments": 0},
    "Quick  🔍 (100 posts, titles only — ~10 sec)": {"posts": 100, "comments": 0},
    "Deep   🔬 (200 posts + comments  — ~30 sec)":  {"posts": 200, "comments": 10},
}


# ── Low-level fetch ──────────────────────────────────────────────────────────

async def _get(session: aiohttp.ClientSession, sem: asyncio.Semaphore, url: str, params: dict) -> Optional[dict]:
    """Retry on rate-limit / transient errors with exponential backoff."""
    async with sem:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        return await r.json(content_type=None)
                    if r.status in (429, 503):
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if r.status in (403, 404):
                        return None   # don't retry
            except (asyncio.TimeoutError, aiohttp.ClientError):
                await asyncio.sleep(1 + attempt)
    return None


# ── Post fetching ────────────────────────────────────────────────────────────

async def _fetch_listing_page(session, sem, subreddit, after, limit):
    params = {"limit": limit, "raw_json": 1}
    if after:
        params["after"] = after
    return await _get(session, sem, f"https://www.reddit.com/r/{subreddit}/new.json", params)


async def _fetch_posts(session, sem, subreddit: str, days: int, max_posts: int) -> list:
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    posts = []
    after = None
    pages_needed = max(1, (max_posts + 99) // 100)   # each page = 100 posts

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
    data = await _get(
        session, sem,
        f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json",
        {"raw_json": 1, "limit": 50, "depth": 1},
    )
    if not data or len(data) < 2:
        return []
    return [
        c["data"]["body"]
        for c in data[1]["data"].get("children", [])
        if c.get("data", {}).get("body", "") not in ("", "[deleted]", "[removed]")
    ]


# ── Per-subreddit scan ───────────────────────────────────────────────────────

async def _scan_one(session, sem, subreddit: str, days: int, max_posts: int, max_comments: int) -> list:
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
                "score":       p.get("score", 0),
            })

    if max_comments > 0 and posts:
        top_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)[:max_comments]
        comment_tasks = [_fetch_comments(session, sem, subreddit, p["id"]) for p in top_posts]
        results = await asyncio.gather(*comment_tasks)
        for p, bodies in zip(top_posts, results):
            for body in bodies:
                items.append({
                    "subreddit":   subreddit,
                    "text":        body,
                    "created_utc": p.get("created_utc", 0),
                    "post_id":     p.get("id", ""),
                    "score":       p.get("score", 0),
                })

    return items


# ── Main entry point ─────────────────────────────────────────────────────────

async def _scan_one_named(session, sem, subreddit, days, max_posts, max_comments):
    """Wraps _scan_one and returns (subreddit, items) so caller doesn't need dict lookup."""
    items = await _scan_one(session, sem, subreddit, days, max_posts, max_comments)
    return subreddit, items


async def _scan_all_async(
    subreddits: list,
    days: int,
    max_posts: int,
    max_comments: int,
    on_progress: Callable,
) -> list:
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
