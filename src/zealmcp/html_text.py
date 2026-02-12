from __future__ import annotations

from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines()]
    compact: list[str] = []
    last_blank = False
    for line in lines:
        if not line:
            if not last_blank and compact:
                compact.append("")
            last_blank = True
            continue
        compact.append(line)
        last_blank = False

    return "\n".join(compact).strip()
