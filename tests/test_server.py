"""Tests for miniflux_mcp.server."""

from __future__ import annotations

import json

import pytest

from miniflux_mcp.server import (
    collapse_non_alnum,
    discover_feeds,
    export_opml,
    fetch_entry_content,
    get_current_user,
    get_entry,
    get_feed,
    get_feed_counters,
    get_feed_entry,
    get_feed_icon,
    get_version,
    healthcheck,
    list_categories,
    list_feeds,
    resolve_id,
    search_entries,
    search_feeds_by_category,
    strip_diacritics,
    to_lower,
    to_unix_seconds,
    tokenize_alnum,
    tokens_are_subset,
)

# ---------------------------------------------------------------------------
# String normalization helpers
# ---------------------------------------------------------------------------


class TestStripDiacritics:
    def test_basic(self):
        assert strip_diacritics("cafe\u0301") == "cafe"

    def test_no_diacritics(self):
        assert strip_diacritics("hello") == "hello"


class TestToLower:
    def test_mixed_case(self):
        assert to_lower("Hello World") == "hello world"

    def test_diacritics(self):
        assert to_lower("Cafe\u0301") == "cafe"


class TestCollapseNonAlnum:
    def test_removes_punctuation(self):
        assert collapse_non_alnum("Hello, World!") == "helloworld"

    def test_keeps_digits(self):
        assert collapse_non_alnum("test-123") == "test123"


class TestTokenizeAlnum:
    def test_basic(self):
        assert tokenize_alnum("Hello, World! 123") == ["hello", "world", "123"]

    def test_empty(self):
        assert tokenize_alnum("") == []


class TestTokensAreSubset:
    def test_subset(self):
        assert tokens_are_subset(["hello"], ["hello", "world"]) is True

    def test_not_subset(self):
        assert tokens_are_subset(["missing"], ["hello", "world"]) is False

    def test_empty_query(self):
        assert tokens_are_subset([], ["hello"]) is False


# ---------------------------------------------------------------------------
# Timestamp conversion
# ---------------------------------------------------------------------------


class TestToUnixSeconds:
    def test_none(self):
        assert to_unix_seconds(None) is None

    def test_empty_string(self):
        assert to_unix_seconds("") is None

    def test_unix_seconds(self):
        assert to_unix_seconds(1700000000) == 1700000000

    def test_unix_milliseconds(self):
        assert to_unix_seconds(1700000000000) == 1700000000

    def test_digit_string(self):
        assert to_unix_seconds("1700000000") == 1700000000

    def test_iso_date(self):
        result = to_unix_seconds("2025-01-15")
        assert result is not None
        assert isinstance(result, int)

    def test_iso_datetime(self):
        result = to_unix_seconds("2025-01-15T10:00:00")
        assert result is not None

    def test_invalid(self):
        assert to_unix_seconds("not-a-date") is None


# ---------------------------------------------------------------------------
# Tool tests
# ---------------------------------------------------------------------------


class TestListCategories:
    async def test_list_categories(self, mock_api):
        result = json.loads(await list_categories())
        assert "categories" in result
        assert len(result["categories"]) == 3
        assert result["categories"][0]["title"] == "Technology"

    async def test_list_categories_with_counts(self, mock_api):
        result = json.loads(await list_categories(counts=True))
        assert "categories" in result


class TestListFeeds:
    async def test_list_feeds(self, mock_api):
        result = json.loads(await list_feeds())
        assert "feeds" in result
        assert len(result["feeds"]) == 2
        assert result["feeds"][0]["title"] == "Hacker News"
        assert result["feeds"][0]["category"]["title"] == "Technology"


class TestSearchFeedsByCategory:
    async def test_no_query(self, mock_api):
        result = json.loads(await search_feeds_by_category(category_id=1))
        assert "feeds" in result
        assert len(result["feeds"]) == 1

    async def test_with_query(self, mock_api):
        result = json.loads(await search_feeds_by_category(category_id=1, query="hacker"))
        feeds = result["feeds"]
        assert len(feeds) == 1
        assert feeds[0]["title"] == "Hacker News"

    async def test_with_query_no_match(self, mock_api):
        result = json.loads(await search_feeds_by_category(category_id=1, query="nonexistent"))
        assert result["feeds"] == []


class TestSearchEntries:
    async def test_global_search(self, mock_api):
        result = json.loads(await search_entries())
        assert result["total"] == 2
        assert len(result["entries"]) == 2
        assert result["has_more"] is False

    async def test_feed_scoped(self, mock_api):
        result = json.loads(await search_entries(feed_id=10))
        assert result["total"] == 2

    async def test_category_scoped(self, mock_api):
        result = json.loads(await search_entries(category_id=1))
        assert result["total"] == 2

    async def test_pagination_fields(self, mock_api):
        result = json.loads(await search_entries(limit=20, offset=0))
        assert "limit" in result
        assert "offset" in result
        assert "next_offset" in result
        assert "has_more" in result


class TestResolveId:
    async def test_resolve_by_name(self, mock_api):
        result = json.loads(await resolve_id(query="Technology"))
        assert result["query"] == "Technology"
        cats = result["matches"]["categories"]
        assert any(c["title"] == "Technology" for c in cats)

    async def test_resolve_by_partial(self, mock_api):
        result = json.loads(await resolve_id(query="tech"))
        cats = result["matches"]["categories"]
        assert any(c["title"] == "Technology" for c in cats)

    async def test_resolve_numeric_id(self, mock_api):
        result = json.loads(await resolve_id(query="1"))
        assert result["exact_id_match"] is not None
        assert result["exact_id_match"]["type"] == "category"
        assert result["exact_id_match"]["id"] == 1

    async def test_resolve_feed_name(self, mock_api):
        result = json.loads(await resolve_id(query="hacker"))
        feeds = result["matches"]["feeds"]
        assert any(f["title"] == "Hacker News" for f in feeds)

    async def test_inferred_kind(self, mock_api):
        result = json.loads(await resolve_id(query="ArXiv"))
        assert result["inferred_kind"] == "feed"

    async def test_no_match(self, mock_api):
        result = json.loads(await resolve_id(query="zzzznonexistent"))
        assert result["matches"]["categories"] == []
        assert result["matches"]["feeds"] == []


# ---------------------------------------------------------------------------
# New tool tests
# ---------------------------------------------------------------------------


class TestGetEntry:
    async def test_get_entry(self, mock_api):
        result = json.loads(await get_entry(entry_id=100))
        assert result["id"] == 100
        assert result["title"] == "Test Article One"
        assert "content" in result


class TestGetFeed:
    async def test_get_feed(self, mock_api):
        result = json.loads(await get_feed(feed_id=10))
        assert result["id"] == 10
        assert result["title"] == "Hacker News"
        assert result["category"]["title"] == "Technology"


class TestGetFeedCounters:
    async def test_get_counters(self, mock_api):
        result = json.loads(await get_feed_counters())
        assert "reads" in result
        assert "unreads" in result
        assert result["unreads"]["10"] == 5


class TestGetFeedEntry:
    async def test_get_feed_entry(self, mock_api):
        result = json.loads(await get_feed_entry(feed_id=10, entry_id=100))
        assert result["id"] == 100
        assert result["feed"]["id"] == 10


class TestFetchEntryContent:
    async def test_fetch_content(self, mock_api):
        result = json.loads(await fetch_entry_content(entry_id=100))
        assert "content" in result
        assert "Original scraped" in result["content"]


class TestGetFeedIcon:
    async def test_get_icon(self, mock_api):
        result = json.loads(await get_feed_icon(feed_id=10))
        assert result["mime_type"] == "image/png"
        assert "data" in result

    async def test_no_icon(self, mock_api):
        import httpx as _httpx

        mock_api.get("/v1/feeds/99/icon").mock(return_value=_httpx.Response(404))
        result = json.loads(await get_feed_icon(feed_id=99))
        assert result["error"] == "no_icon"


class TestDiscoverFeeds:
    async def test_discover(self, mock_api):
        result = json.loads(await discover_feeds(url="https://example.com"))
        assert len(result) == 1
        assert result[0]["title"] == "Example Feed"


class TestGetCurrentUser:
    async def test_get_user(self, mock_api):
        result = json.loads(await get_current_user())
        assert result["username"] == "testuser"
        assert result["id"] == 1


class TestExportOpml:
    async def test_export(self, mock_api):
        result = await export_opml()
        assert "opml" in result


class TestGetVersion:
    async def test_version(self, mock_api):
        result = json.loads(await get_version())
        assert result["version"] == "2.2.6"


class TestHealthcheck:
    async def test_healthcheck(self, mock_api):
        result = await healthcheck()
        assert result == "OK"
