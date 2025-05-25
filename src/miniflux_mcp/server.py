"""Miniflux MCP Server - read-only access to Miniflux RSS reader via MCP."""

from __future__ import annotations

import logging
import math
import os
import unicodedata
from datetime import UTC
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("miniflux-mcp")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _get_base_url() -> str:
    url = os.environ.get("MINIFLUX_BASE_URL", "")
    if not url:
        raise RuntimeError("MINIFLUX_BASE_URL environment variable is required")
    return url.rstrip("/")


def _get_token() -> str | None:
    return os.environ.get("MINIFLUX_TOKEN") or None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _build_client() -> httpx.AsyncClient:
    headers: dict[str, str] = {"Accept": "application/json"}
    token = _get_token()
    if token:
        headers["X-Auth-Token"] = token
    return httpx.AsyncClient(base_url=_get_base_url(), headers=headers, timeout=30.0)


async def _api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    async with _build_client() as client:
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()


async def _api_post(path: str, body: dict[str, Any] | None = None) -> Any:
    async with _build_client() as client:
        resp = await client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()


async def _api_get_text(path: str) -> str:
    async with _build_client() as client:
        resp = await client.get(path)
        resp.raise_for_status()
        return resp.text


# ---------------------------------------------------------------------------
# String normalization for fuzzy matching
# ---------------------------------------------------------------------------


def strip_diacritics(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def to_lower(text: str) -> str:
    return strip_diacritics(text).lower()


def collapse_non_alnum(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]", "", to_lower(text))


def tokenize_alnum(text: str) -> list[str]:
    import re

    return [t for t in re.split(r"[^a-z0-9]+", to_lower(text)) if t]


def tokens_are_subset(query_tokens: list[str], target_tokens: list[str]) -> bool:
    if not query_tokens:
        return False
    target_set = set(target_tokens)
    return all(t in target_set for t in query_tokens)


# ---------------------------------------------------------------------------
# Timestamp conversion
# ---------------------------------------------------------------------------


def to_unix_seconds(value: str | int | float | None) -> int | None:
    if value is None:
        return None

    if isinstance(value, (int, float)) and math.isfinite(value):
        return int(value / 1000 if value > 1e12 else value)

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            n = int(s)
            return int(n / 1000 if n > 1e12 else n)
        # Try ISO / date parsing
        from datetime import datetime

        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return int(dt.timestamp())
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_categories(counts: bool = False) -> str:
    """List all Miniflux categories. Set counts=true to include unread and feed counts (Miniflux 2.0.46+)."""
    params = {"counts": "true"} if counts else None
    categories = await _api_get("/v1/categories", params=params)
    return _json({"categories": categories})


@mcp.tool()
async def list_feeds() -> str:
    """List all feeds for the authenticated user."""
    feeds = await _api_get("/v1/feeds")
    mapped = [
        {
            "id": f["id"],
            "title": f["title"],
            "site_url": f.get("site_url"),
            "feed_url": f.get("feed_url"),
            "category": {"id": f["category"]["id"], "title": f["category"]["title"]} if f.get("category") else None,
        }
        for f in feeds
    ]
    return _json({"feeds": mapped})


@mcp.tool()
async def search_feeds_by_category(category_id: int, query: str | None = None) -> str:
    """Search for feeds within a specific Miniflux category. Optionally filter by title/URL with query."""
    feeds = await _api_get(f"/v1/categories/{category_id}/feeds")
    if query:
        q = query.lower()
        feeds = [
            f
            for f in feeds
            if q in (f.get("title") or "").lower()
            or q in (f.get("site_url") or "").lower()
            or q in (f.get("feed_url") or "").lower()
        ]
    return _json({"feeds": feeds})


def _build_entry_params(
    search: str | None,
    status: str | None,
    starred: bool | None,
    limit: int,
    offset: int,
    order: str,
    direction: str,
    *,
    before: str | None,
    after: str | None,
    published_before: str | None,
    published_after: str | None,
    changed_before: str | None,
    changed_after: str | None,
    before_entry_id: int | None,
    after_entry_id: int | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "limit": max(1, min(limit, 200)),
        "offset": max(0, offset),
        "order": order,
        "direction": direction,
    }
    if search:
        params["search"] = search
    if status:
        valid = {"read", "unread", "removed"}
        for s in status.split(","):
            s = s.strip()
            if s in valid:
                params.setdefault("status", [])
                params["status"].append(s)  # type: ignore[union-attr]
    if starred is not None:
        params["starred"] = str(starred).lower()
    for name, val in [
        ("before", before),
        ("after", after),
        ("published_before", published_before),
        ("published_after", published_after),
        ("changed_before", changed_before),
        ("changed_after", changed_after),
    ]:
        ts = to_unix_seconds(val)
        if ts is not None:
            params[name] = ts
    if before_entry_id is not None:
        params["before_entry_id"] = before_entry_id
    if after_entry_id is not None:
        params["after_entry_id"] = after_entry_id
    return params


def _entries_path(category_id: int | None, feed_id: int | None) -> str:
    if feed_id is not None and category_id is None:
        return f"/v1/feeds/{feed_id}/entries"
    if category_id is not None and feed_id is None:
        return f"/v1/categories/{category_id}/entries"
    return "/v1/entries"


@mcp.tool()
async def search_entries(
    category_id: int | None = None,
    feed_id: int | None = None,
    search: str | None = None,
    status: str | None = None,
    starred: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    order: str = "published_at",
    direction: str = "desc",
    before: str | None = None,
    after: str | None = None,
    published_before: str | None = None,
    published_after: str | None = None,
    changed_before: str | None = None,
    changed_after: str | None = None,
    before_entry_id: int | None = None,
    after_entry_id: int | None = None,
) -> str:
    """Search entries (articles). Global full-text via `search`, or scoped by category_id/feed_id.

    The `search` parameter expects a single keyword or phrase (no boolean operators).
    If a global search returns no results for an ambiguous term, the user may have meant
    a source name -- ask for clarification.
    """
    params = _build_entry_params(
        search, status, starred, limit, offset, order, direction,
        before=before, after=after,
        published_before=published_before, published_after=published_after,
        changed_before=changed_before, changed_after=changed_after,
        before_entry_id=before_entry_id, after_entry_id=after_entry_id,
    )
    path = _entries_path(category_id, feed_id)
    data = await _api_get(path, params=params)
    total = data.get("total", 0)
    entries = data.get("entries", [])
    count = len(entries)
    has_more = offset + count < total

    return _json({
        "total": total,
        "entries": entries,
        "limit": params["limit"],
        "offset": params["offset"],
        "next_offset": offset + count if has_more else None,
        "has_more": has_more,
    })


@mcp.tool()
async def get_entry(entry_id: int) -> str:
    """Get a single entry (article) by its ID. Returns the full content, metadata, and feed info."""
    entry = await _api_get(f"/v1/entries/{entry_id}")
    return _json(entry)


@mcp.tool()
async def get_feed(feed_id: int) -> str:
    """Get full details for a single feed by its ID."""
    feed = await _api_get(f"/v1/feeds/{feed_id}")
    return _json(feed)


@mcp.tool()
async def get_feed_counters() -> str:
    """Get read and unread counters for every feed. Returns a map of feed_id to {read, unread} counts."""
    counters = await _api_get("/v1/feeds/counters")
    return _json(counters)


@mcp.tool()
async def get_feed_entry(feed_id: int, entry_id: int) -> str:
    """Get a specific entry from a specific feed."""
    entry = await _api_get(f"/v1/feeds/{feed_id}/entries/{entry_id}")
    return _json(entry)


@mcp.tool()
async def fetch_entry_content(entry_id: int) -> str:
    """Fetch the original article content for an entry. Miniflux will scrape the original webpage."""
    content = await _api_get(f"/v1/entries/{entry_id}/fetch-content")
    return _json(content)


@mcp.tool()
async def get_feed_icon(feed_id: int) -> str:
    """Get the icon (favicon) for a feed. Returns icon data as base64-encoded string with MIME type."""
    try:
        icon = await _api_get(f"/v1/feeds/{feed_id}/icon")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return _json({"error": "no_icon", "message": f"Feed {feed_id} has no icon"})
        raise
    return _json(icon)


@mcp.tool()
async def discover_feeds(url: str) -> str:
    """Discover RSS/Atom feeds from a website URL. Returns a list of discovered feed subscriptions."""
    result = await _api_post("/v1/discover", {"url": url})
    return _json(result)


@mcp.tool()
async def get_current_user() -> str:
    """Get information about the currently authenticated Miniflux user."""
    user = await _api_get("/v1/me")
    return _json(user)


@mcp.tool()
async def export_opml() -> str:
    """Export all feed subscriptions as OPML (XML format)."""
    opml = await _api_get_text("/v1/export")
    return opml


@mcp.tool()
async def get_version() -> str:
    """Get the Miniflux server version and build information."""
    version = await _api_get("/v1/version")
    return _json(version)


@mcp.tool()
async def healthcheck() -> str:
    """Check if the Miniflux instance is healthy and the database connection is working."""
    result = await _api_get_text("/healthcheck")
    return result


def _fuzzy_score(
    title: str, item_id: int, *, q_lower: str, q_collapsed: str, q_tokens: list[str], numeric_id: int | None
) -> int:
    lower = to_lower(title)
    collapsed = collapse_non_alnum(title)
    tokens = tokenize_alnum(title)
    s = 0
    if numeric_id is not None and item_id == numeric_id:
        s = max(s, 90)
    if lower == q_lower:
        s = max(s, 100)
    if collapsed == q_collapsed and q_collapsed:
        s = max(s, 70)
    if tokens_are_subset(q_tokens, tokens):
        s = max(s, 50)
    if q_lower and q_lower in lower:
        s = max(s, 30)
    return s


def _score_and_filter(
    items: list[dict[str, Any]], limit_per: int, **kwargs: Any
) -> list[dict[str, Any]]:
    scored = sorted(
        [(item, _fuzzy_score(item["title"], item["id"], **kwargs)) for item in items],
        key=lambda x: (-x[1], x[0]["title"]),
    )
    return [{"id": item["id"], "title": item["title"], "score": s} for item, s in scored if s >= 30][:limit_per]


@mcp.tool()
async def resolve_id(query: str, limit: int = 10) -> str:
    """Fuzzy-resolve a user-supplied name or numeric ID to matching categories and feeds.

    Always searches both types. Returns scored matches.
    """
    q_raw = query.strip()
    q_lower = to_lower(q_raw)
    q_collapsed = collapse_non_alnum(q_raw)
    q_tokens = tokenize_alnum(q_raw)
    numeric_id = int(q_raw) if q_raw.isdigit() else None
    limit_per = min(max(1, limit), 25)

    try:
        categories, feeds = await _fetch_categories_and_feeds()
    except Exception as e:
        return _json({"isError": True, "error": "FETCH_FAILED", "message": str(e)})

    score_kwargs = {"q_lower": q_lower, "q_collapsed": q_collapsed, "q_tokens": q_tokens, "numeric_id": numeric_id}
    cat_matches = _score_and_filter(categories, limit_per, **score_kwargs)
    feed_matches = _score_and_filter(feeds, limit_per, **score_kwargs)

    inferred_kind = None
    if cat_matches and not feed_matches:
        inferred_kind = "category"
    elif feed_matches and not cat_matches:
        inferred_kind = "feed"

    exact_id_match = None
    if numeric_id is not None:
        if any(c["id"] == numeric_id for c in categories):
            exact_id_match = {"type": "category", "id": numeric_id}
        elif any(f["id"] == numeric_id for f in feeds):
            exact_id_match = {"type": "feed", "id": numeric_id}

    return _json({
        "query": q_raw,
        "inferred_kind": inferred_kind,
        "exact_id_match": exact_id_match,
        "matches": {"categories": cat_matches, "feeds": feed_matches},
        "truncated": False,
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_categories_and_feeds() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    async with _build_client() as client:
        cat_resp, feed_resp = await client.get("/v1/categories"), await client.get("/v1/feeds")
        cat_resp.raise_for_status()
        feed_resp.raise_for_status()
        return cat_resp.json(), feed_resp.json()


def _json(data: Any) -> str:
    import json

    return json.dumps(data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
