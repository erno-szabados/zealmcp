from __future__ import annotations

import argparse
import asyncio

from .config import load_settings
from .server import build_server, run_stdio


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP stdio server exposing Zeal docsets")
    parser.parse_args()

    settings = load_settings()
    server = build_server(settings)
    asyncio.run(run_stdio(server))
