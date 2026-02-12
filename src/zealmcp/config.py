from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    docsets_paths: tuple[str, ...]
    max_chars: int = 20_000


def load_settings() -> Settings:
    raw_paths = os.environ.get("ZEAL_DOCSETS_PATH", "").strip()
    if not raw_paths:
        raise RuntimeError(
            "ZEAL_DOCSETS_PATH is not set. Provide one or more directories containing *.docset folders."
        )

    parts = [p.strip() for p in raw_paths.split(os.pathsep) if p.strip()]
    if not parts:
        raise RuntimeError(
            "ZEAL_DOCSETS_PATH is empty. Provide one or more directories containing *.docset folders."
        )

    return Settings(docsets_paths=tuple(parts))
