"""Shared fixtures for miniflux_mcp tests."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import pytest
import respx

# Ensure env vars are set for all tests
os.environ.setdefault("MINIFLUX_BASE_URL", "https://miniflux.test")
os.environ.setdefault("MINIFLUX_TOKEN", "test-token-123")


SAMPLE_CATEGORIES: list[dict[str, Any]] = [
    {"id": 1, "title": "Technology", "user_id": 1},
    {"id": 2, "title": "Science", "user_id": 1},
    {"id": 3, "title": "News", "user_id": 1},
]

SAMPLE_FEEDS: list[dict[str, Any]] = [
    {
        "id": 10,
        "title": "Hacker News",
        "site_url": "https://news.ycombinator.com",
        "feed_url": "https://news.ycombinator.com/rss",
        "user_id": 1,
        "category": {"id": 1, "title": "Technology"},
    },
    {
        "id": 20,
        "title": "ArXiv CS",
        "site_url": "https://arxiv.org",
        "feed_url": "https://arxiv.org/rss/cs",
        "user_id": 1,
        "category": {"id": 2, "title": "Science"},
    },
]

SAMPLE_ENTRY: dict[str, Any] = {
    "id": 100,
    "title": "Test Article One",
    "url": "https://example.com/1",
    "content": "<p>Full article content here</p>",
    "status": "unread",
    "starred": False,
    "published_at": "2025-01-15T10:00:00Z",
    "feed": {"id": 10, "title": "Hacker News"},
}

SAMPLE_FEED_DETAIL: dict[str, Any] = {
    "id": 10,
    "title": "Hacker News",
    "site_url": "https://news.ycombinator.com",
    "feed_url": "https://news.ycombinator.com/rss",
    "user_id": 1,
    "checked_at": "2025-01-15T12:00:00Z",
    "parsing_error_count": 0,
    "category": {"id": 1, "title": "Technology"},
}

SAMPLE_COUNTERS: dict[str, Any] = {
    "reads": {"10": 42, "20": 10},
    "unreads": {"10": 5, "20": 3},
}

SAMPLE_ICON: dict[str, Any] = {
    "id": 1,
    "data": "image/png;base64,iVBORw0KGgo=",
    "mime_type": "image/png",
}

SAMPLE_DISCOVER: list[dict[str, Any]] = [
    {"url": "https://example.com/feed.xml", "title": "Example Feed", "type": "rss"},
]

SAMPLE_USER: dict[str, Any] = {
    "id": 1,
    "username": "testuser",
    "is_admin": False,
    "language": "en_US",
    "timezone": "UTC",
}

SAMPLE_VERSION: dict[str, Any] = {
    "version": "2.2.6",
    "commit": "abc123",
    "build_date": "2025-01-15T00:00:00Z",
}

SAMPLE_FETCH_CONTENT: dict[str, Any] = {
    "content": "<p>Original scraped article content</p>",
}

SAMPLE_ENTRIES_RESPONSE: dict[str, Any] = {
    "total": 2,
    "entries": [
        {
            "id": 100,
            "title": "Test Article One",
            "url": "https://example.com/1",
            "content": "Content one",
            "status": "unread",
            "starred": False,
            "published_at": "2025-01-15T10:00:00Z",
            "feed": {"id": 10, "title": "Hacker News"},
        },
        {
            "id": 101,
            "title": "Test Article Two",
            "url": "https://example.com/2",
            "content": "Content two",
            "status": "read",
            "starred": True,
            "published_at": "2025-01-14T10:00:00Z",
            "feed": {"id": 10, "title": "Hacker News"},
        },
    ],
}


@pytest.fixture()
def mock_api():
    """Mock Miniflux API responses using respx."""
    with respx.mock(base_url="https://miniflux.test", assert_all_called=False) as router:
        router.get("/v1/categories").mock(
            return_value=httpx.Response(200, json=SAMPLE_CATEGORIES),
        )
        router.get("/v1/feeds").mock(
            return_value=httpx.Response(200, json=SAMPLE_FEEDS),
        )
        router.get("/v1/categories/1/feeds").mock(
            return_value=httpx.Response(200, json=[SAMPLE_FEEDS[0]]),
        )
        router.get("/v1/entries").mock(
            return_value=httpx.Response(200, json=SAMPLE_ENTRIES_RESPONSE),
        )
        router.get("/v1/feeds/10/entries").mock(
            return_value=httpx.Response(200, json=SAMPLE_ENTRIES_RESPONSE),
        )
        router.get("/v1/categories/1/entries").mock(
            return_value=httpx.Response(200, json=SAMPLE_ENTRIES_RESPONSE),
        )
        router.get("/v1/entries/100").mock(
            return_value=httpx.Response(200, json=SAMPLE_ENTRY),
        )
        router.get("/v1/feeds/10").mock(
            return_value=httpx.Response(200, json=SAMPLE_FEED_DETAIL),
        )
        router.get("/v1/feeds/counters").mock(
            return_value=httpx.Response(200, json=SAMPLE_COUNTERS),
        )
        router.get("/v1/feeds/10/entries/100").mock(
            return_value=httpx.Response(200, json=SAMPLE_ENTRY),
        )
        router.get("/v1/entries/100/fetch-content").mock(
            return_value=httpx.Response(200, json=SAMPLE_FETCH_CONTENT),
        )
        router.get("/v1/feeds/10/icon").mock(
            return_value=httpx.Response(200, json=SAMPLE_ICON),
        )
        router.post("/v1/discover").mock(
            return_value=httpx.Response(200, json=SAMPLE_DISCOVER),
        )
        router.get("/v1/me").mock(
            return_value=httpx.Response(200, json=SAMPLE_USER),
        )
        router.get("/v1/export").mock(
            return_value=httpx.Response(200, text='<?xml version="1.0"?><opml/>'),
        )
        router.get("/v1/version").mock(
            return_value=httpx.Response(200, json=SAMPLE_VERSION),
        )
        router.get("/healthcheck").mock(
            return_value=httpx.Response(200, text="OK"),
        )
        yield router
