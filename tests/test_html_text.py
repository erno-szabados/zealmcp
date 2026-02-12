from __future__ import annotations

from zealmcp.html_text import html_to_text


def test_html_to_text_strips_scripts() -> None:
    html = "<html><body><script>alert(1)</script><h1>Title</h1><p>Hi</p></body></html>"
    text = html_to_text(html)
    assert "alert" not in text
    assert "Title" in text
    assert "Hi" in text
