from __future__ import annotations

import sqlite3
from pathlib import Path

from zealmcp.docsets import Docset, discover_docsets, search_docset


def _make_docset(tmp_path: Path, name: str) -> Path:
    root = tmp_path / f"{name}.docset"
    dsidx = root / "Contents" / "Resources" / "docSet.dsidx"
    docs = root / "Contents" / "Resources" / "Documents"
    docs.mkdir(parents=True)

    dsidx.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(dsidx)
    conn.execute("CREATE TABLE searchIndex (name TEXT, type TEXT, path TEXT)")
    conn.execute("INSERT INTO searchIndex VALUES ('Foo', 'Guide', 'foo.html')")
    conn.execute("INSERT INTO searchIndex VALUES ('Foobar', 'Guide', 'foobar.html')")
    conn.commit()
    conn.close()

    (docs / "foo.html").write_text("<html><body><h1>Foo</h1><p>Hello</p></body></html>")
    (docs / "foobar.html").write_text("<html><body><h1>Foobar</h1></body></html>")

    return root


def test_discover_docsets(tmp_path: Path) -> None:
    _make_docset(tmp_path, "Test")
    docsets = discover_docsets([str(tmp_path)])
    assert len(docsets) == 1
    assert docsets[0].name.lower().startswith("test")


def test_search_docset(tmp_path: Path) -> None:
    _make_docset(tmp_path, "Test")
    docsets = discover_docsets([str(tmp_path)])
    d = docsets[0]
    results = search_docset(d, "Foo", limit=10)
    assert results
    assert results[0].title == "Foo"
