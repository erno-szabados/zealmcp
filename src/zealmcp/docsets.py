from __future__ import annotations

import plistlib
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Docset:
    id: str
    name: str
    root: Path
    dsidx_path: Path
    documents_path: Path


def _safe_docset_id(name: str) -> str:
    normalized = "".join(
        ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in name.strip()
    )
    normalized = "-".join(filter(None, normalized.split("-")))
    return normalized.lower() or "docset"


def discover_docsets(docsets_dirs: Iterable[str]) -> list[Docset]:
    docsets: list[Docset] = []

    for base in docsets_dirs:
        base_path = Path(base).expanduser()
        if not base_path.exists() or not base_path.is_dir():
            continue

        for docset_root in sorted(base_path.glob("*.docset")):
            if not docset_root.is_dir():
                continue

            contents = docset_root / "Contents"
            resources = contents / "Resources"
            dsidx = resources / "docSet.dsidx"
            documents = resources / "Documents"
            if not dsidx.exists() or not documents.exists():
                continue

            name = docset_root.stem
            info_plist = contents / "Info.plist"
            if info_plist.exists():
                try:
                    with info_plist.open("rb") as f:
                        info = plistlib.load(f)
                    # Prefer Dash-style keys when available.
                    name = (
                        info.get("CFBundleDisplayName")
                        or info.get("CFBundleName")
                        or info.get("DocSetPlatformFamily")
                        or name
                    )
                except Exception:
                    pass

            docset_id = _safe_docset_id(name)
            docsets.append(
                Docset(
                    id=docset_id,
                    name=str(name),
                    root=docset_root,
                    dsidx_path=dsidx,
                    documents_path=documents,
                )
            )

    # Ensure stable ordering and uniqueness by id.
    unique: dict[str, Docset] = {}
    for d in docsets:
        if d.id in unique:
            # De-duplicate by including parent directory name.
            suffix = _safe_docset_id(d.root.parent.name)
            alt_id = f"{d.id}-{suffix}"
            unique.setdefault(alt_id, Docset(**{**d.__dict__, "id": alt_id}))
        else:
            unique[d.id] = d

    return sorted(unique.values(), key=lambda d: d.name.lower())


@dataclass(frozen=True)
class SearchResult:
    docset_id: str
    docset_name: str
    title: str
    entry_type: str | None
    path: str
    source_uri: str


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    # Use SQLite URI mode for readonly.
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _get_search_table(conn: sqlite3.Connection) -> str:
    # Most docsets use 'searchIndex'. Some use 'searchIndex' with different casing.
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    if "searchIndex" in tables:
        return "searchIndex"
    for t in tables:
        if t.lower() == "searchindex":
            return t
    raise RuntimeError("Docset index missing searchIndex table")


def search_docset(docset: Docset, query: str, limit: int) -> list[SearchResult]:
    q = query.strip()
    if not q:
        return []

    conn = _connect_readonly(docset.dsidx_path)
    try:
        table = _get_search_table(conn)
        # Fetch more than limit; rank in Python for nicer results.
        fetch_n = max(limit * 5, limit)
        like_any = f"%{q}%"
        cur = conn.execute(
            f"SELECT name, type, path FROM {table} WHERE name LIKE ? LIMIT ?",
            (like_any, fetch_n),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    def score(name: str) -> tuple[int, int]:
        n = name.lower()
        qq = q.lower()
        if n == qq:
            return (0, len(n))
        if n.startswith(qq):
            return (1, len(n))
        idx = n.find(qq)
        if idx >= 0:
            return (2, idx)
        return (3, len(n))

    ranked = sorted(rows, key=lambda r: score(r[0]))[:limit]

    out: list[SearchResult] = []
    for name, typ, path in ranked:
        source_uri = f"zeal://docset/{docset.id}/doc/{path}"
        out.append(
            SearchResult(
                docset_id=docset.id,
                docset_name=docset.name,
                title=name,
                entry_type=typ,
                path=path,
                source_uri=source_uri,
            )
        )
    return out


def load_entry_html(docset: Docset, path: str) -> tuple[str, Path]:
    # Dash stores relative paths within Documents.
    rel = path.lstrip("/")
    # Some docsets include anchors/query params in the index path.
    # The on-disk file path is the part before '?' and '#'.
    rel = rel.split("?", 1)[0].split("#", 1)[0]
    full = (docset.documents_path / rel).resolve()

    # Prevent escaping the Documents directory.
    docs_root = docset.documents_path.resolve()
    if docs_root not in full.parents and full != docs_root:
        raise RuntimeError("Invalid entry path")

    if not full.exists() or not full.is_file():
        raise FileNotFoundError(rel)

    return full.read_text(encoding="utf-8", errors="replace"), full


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[TRUNCATED]"
