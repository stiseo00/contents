from __future__ import annotations

import asyncio
import calendar
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

import feedparser
import httpx
from zoneinfo import ZoneInfo

from ..models import FeedItem
from . import og, providers, summarizer


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InterestCrawler/1.0; +https://example.com)"
}


def _hash_id(category: str, url: str) -> str:
    return hashlib.sha256(f"{category}{url}".encode("utf-8")).hexdigest()


def _struct_time_to_dt(struct_time) -> Optional[datetime]:
    if not struct_time:
        return None
    try:
        ts = calendar.timegm(struct_time)
    except Exception:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _parse_entry_date(entry) -> Optional[datetime]:
    dt = _struct_time_to_dt(entry.get("published_parsed"))
    if dt:
        return dt
    dt = _struct_time_to_dt(entry.get("updated_parsed"))
    return dt


def _extract_entry_image(entry) -> str:
    media_thumb = entry.get("media_thumbnail")
    if isinstance(media_thumb, list) and media_thumb:
        url = media_thumb[0].get("url")
        if url:
            return url
    media_content = entry.get("media_content")
    if isinstance(media_content, list) and media_content:
        url = media_content[0].get("url")
        if url:
            return url
    if entry.get("image") and isinstance(entry.get("image"), dict):
        url = entry["image"].get("href")
        if url:
            return url
    return ""


def _normalize_url(url: str) -> str:
    return url.strip()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


async def fetch_and_enrich(categories: Sequence[str]) -> List[FeedItem]:
    kst = ZoneInfo("Asia/Seoul")
    today_kst = datetime.now(kst).date()
    fetched_at = datetime.now(kst).isoformat()

    items: List[FeedItem] = []
    seen_url: Set[str] = set()
    seen_title_domain: Set[Tuple[str, str]] = set()

    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        for category in categories:
            rss_urls = providers.get_rss_urls(category)
            for rss_url in rss_urls:
                try:
                    resp = await client.get(rss_url)
                    resp.raise_for_status()
                except Exception:
                    continue
                feed = feedparser.parse(resp.text)
                for entry in feed.entries:
                    url = entry.get("link") or entry.get("id")
                    if not url:
                        continue
                    url = _normalize_url(url)
                    if url in seen_url:
                        continue
                    title = (entry.get("title") or "").strip()
                    domain = _domain(url)
                    if title:
                        key = (title.lower(), domain)
                        if key in seen_title_domain:
                            continue
                    published_dt = _parse_entry_date(entry)
                    if not published_dt:
                        continue
                    published_kst = published_dt.astimezone(kst)
                    if published_kst.date() != today_kst:
                        continue

                    summary_raw = entry.get("summary") or entry.get("description") or ""
                    summary = summarizer.naive_summary(summary_raw, 320) if summary_raw else ""
                    image_url = _extract_entry_image(entry)
                    source = None
                    if isinstance(entry.get("source"), dict):
                        source = entry.get("source", {}).get("title")
                    if not source:
                        source = feed.feed.get("title") if feed and feed.feed else None
                    if not source:
                        source = domain or ""

                    item = FeedItem(
                        id=_hash_id(category, url),
                        category=category,
                        title=title or url,
                        url=url,
                        source=source or "",
                        published_at=published_kst.isoformat(),
                        image_url=image_url or "",
                        summary=summary or "",
                        fetched_at=fetched_at,
                    )
                    items.append(item)
                    seen_url.add(url)
                    if title:
                        seen_title_domain.add((title.lower(), domain))

        await _enrich_items(items, client)

    for item in items:
        if not item.summary:
            item.summary = ""
        if not item.image_url:
            item.image_url = ""
    return items


async def _enrich_items(items: List[FeedItem], client: httpx.AsyncClient) -> None:
    if not items:
        return
    semaphore = asyncio.Semaphore(6)

    async def _enrich(item: FeedItem) -> None:
        if item.image_url and item.summary:
            return
        async with semaphore:
            data = await og.fetch_og(client, item.url)
        if not item.image_url:
            item.image_url = data.get("image", "") if data else ""
        if not item.summary:
            og_desc = data.get("description", "") if data else ""
            if og_desc:
                item.summary = summarizer.naive_summary(og_desc, 320)

    await asyncio.gather(*[_enrich(item) for item in items])
