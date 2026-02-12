from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

from mcp import types as mtypes
from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from .config import Settings
from .docsets import discover_docsets, load_entry_html, search_docset, truncate_text
from .html_text import html_to_text


def build_server(settings: Settings) -> Server:
    server = Server("zealmcp")

    docsets = {d.id: d for d in discover_docsets(settings.docsets_paths)}

    async def _list_docsets() -> dict[str, Any]:
        return {"docsets": [
            {
                "id": d.id,
                "name": d.name,
                "root": str(d.root),
            }
            for d in docsets.values()
        ]}

    async def _search(
        query: str, docset: str | None = None, limit: int = 10
    ) -> dict[str, Any]:
        lim = max(1, min(int(limit), 50))
        q = (query or "").strip()
        if not q:
            return {"results": []}

        if docset and docset != "all":
            d = docsets.get(docset)
            if not d:
                raise ValueError(f"Unknown docset id: {docset}")
            results = search_docset(d, q, lim)
        else:
            # Search across all docsets; keep best results per-docset in order.
            collected = []
            for d in docsets.values():
                try:
                    collected.extend(search_docset(d, q, lim))
                except Exception:
                    # Some docsets may not have a searchIndex table.
                    continue
            results = collected[:lim]

        return {"results": [asdict(r) for r in results]}

    async def _get_entry(docset: str, path: str, max_chars: int | None = None) -> dict[str, Any]:
        d = docsets.get(docset)
        if not d:
            raise ValueError(f"Unknown docset id: {docset}")

        html, full_path = load_entry_html(d, path)
        text = html_to_text(html)
        mc = settings.max_chars if max_chars is None else int(max_chars)
        text = truncate_text(text, mc)

        return {"entry": {
            "docset_id": d.id,
            "docset_name": d.name,
            "path": path,
            "source_uri": f"zeal://docset/{d.id}/doc/{path}",
            "file": str(full_path),
            "text": text,
        }}

    # Register tool definitions
    @server.list_tools()
    async def _list_tools():
        return [
            mtypes.Tool(
                name="list_docsets",
                title="List docsets",
                description="List discovered Zeal docsets",
                inputSchema={"type": "object"},
            ),
            mtypes.Tool(
                name="search",
                title="Search docset",
                description="Search entries in a docset",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "docset": {"type": ["string", "null"]},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            ),
            mtypes.Tool(
                name="get_entry",
                title="Get entry",
                description="Get an entry from a docset",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "docset": {"type": "string"},
                        "path": {"type": "string"},
                        "max_chars": {"type": ["integer", "null"]},
                    },
                    "required": ["docset", "path"],
                },
            ),
        ]

    # Single dispatcher for tool calls over MCP
    @server.call_tool(validate_input=False)
    async def _call_tool(name: str, arguments: dict[str, Any] | None = None):
        args = arguments or {}
        if name == "list_docsets":
            return await _list_docsets()
        if name == "search":
            q = args.get("query") or args.get("q") or ""
            ds = args.get("docset")
            lim = args.get("limit", 10)
            return await _search(q, ds, lim)
        if name == "get_entry":
            d = args.get("docset")
            p = args.get("path")
            mc = args.get("max_chars")
            return await _get_entry(d, p, mc)
        return mtypes.CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {name}")],
            isError=True,
        )

    @server.read_resource()
    async def _read_resource(uri):
        uri_str = str(uri)
        parsed = urlparse(uri_str)
        # Support zeal://docsets and zeal://docset/{id}/doc/{path}
        if parsed.scheme != "zeal":
            raise ValueError("Invalid zeal URI")

        if parsed.netloc == "docsets" and parsed.path in ("", "/"):
            items = await _list_docsets()
            return [
                ReadResourceContents(
                    content=json.dumps(items, ensure_ascii=False, indent=2),
                    mime_type="application/json",
                )
            ]

        if parsed.netloc == "docset":
            # parsed.path: /{id}/doc/{path}
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) < 2:
                raise ValueError("Invalid zeal URI")
            docset_id = parts[0]
            if parts[1] != "doc":
                raise ValueError("Invalid zeal URI")
            # Note: fragment and query are ignored for on-disk reads.
            doc_path = "/".join(parts[2:])

            d = docsets.get(docset_id)
            if not d:
                raise FileNotFoundError(docset_id)

            html, full_path = load_entry_html(d, doc_path)
            text = html_to_text(html)
            text = truncate_text(text, settings.max_chars)
            return [
                ReadResourceContents(
                    content=text,
                    mime_type="text/plain",
                    meta={"file": str(full_path)},
                )
            ]

    return server


async def run_stdio(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
