from __future__ import annotations

from typing import List
from urllib.parse import quote_plus

from ..models import CATEGORY_KEYWORDS


def google_news_rss_url(query: str) -> str:
    encoded = quote_plus(query)
    return (
        "https://news.google.com/rss/search?q="
        f"{encoded}&hl=ko&gl=KR&ceid=KR:ko"
    )


def get_rss_urls(category: str) -> List[str]:
    keywords = CATEGORY_KEYWORDS.get(category, [])
    if not keywords:
        return []
    query = " OR ".join(keywords) + " when:1d"
    return [google_news_rss_url(query)]
