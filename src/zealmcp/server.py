from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from .config import Settings
from .docsets import discover_docsets, load_entry_html, search_docset, truncate_text
from .html_text import html_to_text


def build_server(settings: Settings) -> Server:
    server = Server("zealmcp")

    docsets = {d.id: d for d in discover_docsets(settings.docsets_paths)}

    @server.tool()
    async def list_docsets() -> list[dict[str, Any]]:
        return [
            {
                "id": d.id,
                "name": d.name,
                "root": str(d.root),
            }
            for d in docsets.values()
        ]

    @server.tool()
    async def search(query: str, docset: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 50))
        q = (query or "").strip()
        if not q:
            return []

        if docset and docset != "all":
            d = docsets.get(docset)
            if not d:
                raise ValueError(f"Unknown docset id: {docset}")
            results = search_docset(d, q, lim)
        else:
            # Search across all docsets; keep best results per-docset in order.
            collected = []
            for d in docsets.values():
                collected.extend(search_docset(d, q, lim))
            results = collected[:lim]

        return [asdict(r) for r in results]

    @server.tool()
    async def get_entry(docset: str, path: str, max_chars: int | None = None) -> dict[str, Any]:
        d = docsets.get(docset)
        if not d:
            raise ValueError(f"Unknown docset id: {docset}")

        html, full_path = load_entry_html(d, path)
        text = html_to_text(html)
        mc = settings.max_chars if max_chars is None else int(max_chars)
        text = truncate_text(text, mc)

        return {
            "docset_id": d.id,
            "docset_name": d.name,
            "path": path,
            "source_uri": f"zeal://docset/{d.id}/doc/{path}",
            "file": str(full_path),
            "text": text,
        }

    @server.resource("zeal://docsets")
    async def res_docsets() -> list[TextContent]:
        # Minimal resource mirror for clients that prefer resources.
        items = await list_docsets()
        return [TextContent(type="text", text=str(items))]

    return server


async def run_stdio(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
