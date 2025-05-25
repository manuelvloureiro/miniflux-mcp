# miniflux-mcp

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server for the [Miniflux](https://miniflux.app) RSS reader. Exposes your feeds, categories, and articles as MCP tools so AI assistants like Claude can browse and search your RSS content.

Based on [tan-yong-sheng/miniflux-mcp](https://github.com/tan-yong-sheng/miniflux-mcp) (TypeScript), rewritten in Python.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A running Miniflux instance (v2.0.46+ recommended for category counts)
- A Miniflux API token

## Quick Start

```bash
git clone <repo-url>
cd miniflux-mcp

# Create your environment file
cp .env.example .env
```

Edit `.env` with your Miniflux instance URL and API token:

```
MINIFLUX_BASE_URL=https://your-miniflux-instance.com
MINIFLUX_TOKEN=your-api-token-here
```

To generate an API token, go to your Miniflux instance: **Settings > API Keys > Create a new API key**.

Install dependencies:

```bash
uv sync --group dev
```

## Configuration

### Claude Code (all sessions)

Create or edit `~/.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "miniflux": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/miniflux-mcp", "miniflux-mcp"],
      "env": {
        "MINIFLUX_BASE_URL": "https://your-miniflux-instance.com",
        "MINIFLUX_TOKEN": "your-api-token"
      }
    }
  }
}
```

Restart Claude Code for the server to load. The miniflux tools will then be available in every session.

### Claude Code (single project)

Create `.mcp.json` in the project root with the same structure as above. The server will only be available when working in that project.

### Claude Desktop

Add the same `miniflux` entry to the MCP servers section in Claude Desktop settings:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Direct execution (for testing)

```bash
# Via entry point
miniflux-mcp

# Via module
python -m miniflux_mcp
```

The server communicates over stdio and is not meant to be used interactively -- it's designed to be launched by an MCP client.

## Available Tools

### list_categories

List all Miniflux categories. Optionally include unread and feed counts.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `counts` | bool | `false` | Include unread/feed counts (Miniflux 2.0.46+) |

### list_feeds

List all feeds for the authenticated user. Returns feed ID, title, site URL, feed URL, and category info.

No parameters.

### search_feeds_by_category

Find feeds within a specific category, optionally filtered by a text query.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `category_id` | int | yes | Numeric category ID |
| `query` | string | no | Filter by title, site URL, or feed URL (case-insensitive) |

### search_entries

Search articles globally or scoped to a category/feed. Supports full-text search, status filtering, date ranges, and pagination.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search` | string | | Full-text search query (single keyword or phrase) |
| `category_id` | int | | Scope to a category |
| `feed_id` | int | | Scope to a feed |
| `status` | string | | Filter by status: `read`, `unread`, `removed` (comma-separated) |
| `starred` | bool | | Filter by bookmarked status |
| `limit` | int | `20` | Max entries to return (1-200) |
| `offset` | int | `0` | Entries to skip for pagination |
| `order` | string | `published_at` | Sort field: `id`, `status`, `published_at`, `category_title`, `category_id` |
| `direction` | string | `desc` | Sort direction: `asc` or `desc` |
| `before` | string | | Entries created before this time (Unix timestamp or `YYYY-MM-DD` / ISO) |
| `after` | string | | Entries created after this time |
| `published_before` | string | | Entries published before this time |
| `published_after` | string | | Entries published after this time |
| `changed_before` | string | | Entries changed before this time |
| `changed_after` | string | | Entries changed after this time |
| `before_entry_id` | int | | Cursor pagination: entries older than this ID |
| `after_entry_id` | int | | Cursor pagination: entries newer than this ID |

### resolve_id

Fuzzy-match a user-supplied name or numeric ID to categories and feeds. Useful when you know a name but not the numeric ID.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string | | Name fragment or numeric ID to resolve |
| `limit` | int | `10` | Max matches per type (max 25) |

Returns scored matches for both categories and feeds, with an `inferred_kind` when the match is unambiguous.

## Example Prompts

Once the MCP server is connected, you can ask Claude things like:

- "What are my RSS categories?"
- "Show me the latest articles from Hacker News"
- "Search for articles about machine learning published this week"
- "What feeds do I have in the Technology category?"
- "Find the feed ID for John Doe's blog"
- "Show me unread articles from today"

## Development

```bash
make setup      # install deps + pre-commit hooks
make test       # pytest with 80% coverage gate
make test-quick # stop on first failure
make lint       # ruff check
make format     # ruff format
make typecheck  # pyright
make review     # all quality gates (lint + typecheck + test)
make clean      # remove build artifacts
```

## Project Structure

```
src/miniflux_mcp/
    __init__.py     # package version
    __main__.py     # python -m entry point
    server.py       # FastMCP server with all tools and API client
tests/
    conftest.py     # respx mock fixtures for Miniflux API
    test_server.py  # 35 tests covering all tools and helpers
```

## License

MIT
