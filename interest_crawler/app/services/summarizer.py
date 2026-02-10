from __future__ import annotations

import re
from bs4 import BeautifulSoup


_whitespace = re.compile(r"\s+")


def naive_summary(html_text: str, max_len: int = 320) -> str:
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = _whitespace.sub(" ", text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
