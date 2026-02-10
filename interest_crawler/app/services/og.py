from __future__ import annotations

from typing import Dict

import httpx
from bs4 import BeautifulSoup


async def fetch_og(client: httpx.AsyncClient, url: str) -> Dict[str, str]:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except Exception:
        return {}

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        og_image = _get_meta(soup, "property", "og:image")
        og_desc = _get_meta(soup, "property", "og:description")
        if not og_desc:
            og_desc = _get_meta(soup, "name", "description")
        return {
            "image": og_image or "",
            "description": og_desc or "",
        }
    except Exception:
        return {}


def _get_meta(soup: BeautifulSoup, attr: str, value: str) -> str:
    tag = soup.find("meta", attrs={attr: value})
    if not tag:
        return ""
    content = tag.get("content")
    return content.strip() if content else ""
