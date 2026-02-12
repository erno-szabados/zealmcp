# zealmcp

An MCP (Model Context Protocol) stdio server that exposes Zeal/Dash docsets for agent grounding.

## Requirements

- Python 3.11+
- `uv`

## Configure

Set `ZEAL_DOCSETS_PATH` to one or more directories containing `*.docset` folders (colon-separated on Linux).

Example:

```bash
export ZEAL_DOCSETS_PATH="$HOME/.local/share/Zeal/Zeal/docsets"
```

## Run

```bash
uv sync
ZEAL_DOCSETS_PATH=... uv run zeal-mcp
```

## MCP tools (MVP)

- `list_docsets` – enumerate discovered docsets
- `search` – search entries in a docset (or across all docsets)
- `get_entry` – load an entry, return plain text plus a stable `source_uri`
