from __future__ import annotations

import json
import sqlite3
from typing import Iterable, List, Sequence

from zoneinfo import ZoneInfo
from datetime import datetime

from .models import FeedItem


def get_kst_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul"))


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_prefs (
                user_id TEXT PRIMARY KEY,
                categories TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_items (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                published_at TEXT NOT NULL,
                image_url TEXT,
                summary TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_prefs(conn: sqlite3.Connection, user_id: str) -> List[str]:
    row = conn.execute(
        "SELECT categories FROM user_prefs WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return []
    try:
        categories = json.loads(row["categories"])
    except json.JSONDecodeError:
        return []
    return categories if isinstance(categories, list) else []


def set_user_prefs(conn: sqlite3.Connection, user_id: str, categories: Sequence[str]) -> None:
    payload = json.dumps(list(categories), ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO user_prefs (user_id, categories, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            categories = excluded.categories,
            updated_at = excluded.updated_at
        """,
        (user_id, payload, get_kst_now().isoformat()),
    )
    conn.commit()


def upsert_feed_items(conn: sqlite3.Connection, items: Iterable[FeedItem]) -> None:
    rows = [
        (
            item.id,
            item.category,
            item.title,
            item.url,
            item.source,
            item.published_at,
            item.image_url,
            item.summary,
            item.fetched_at,
        )
        for item in items
    ]
    if not rows:
        return
    conn.executemany(
        """
        INSERT INTO feed_items (
            id, category, title, url, source, published_at, image_url, summary, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            source = excluded.source,
            published_at = excluded.published_at,
            image_url = excluded.image_url,
            summary = excluded.summary,
            fetched_at = excluded.fetched_at
        """,
        rows,
    )
    conn.commit()


def get_items_for_categories_today(
    conn: sqlite3.Connection,
    categories: Sequence[str],
    today_kst: datetime,
) -> List[dict]:
    if not categories:
        return []
    placeholders = ",".join("?" for _ in categories)
    rows = conn.execute(
        f"SELECT * FROM feed_items WHERE category IN ({placeholders}) ORDER BY published_at DESC",
        tuple(categories),
    ).fetchall()
    today_prefix = today_kst.date().isoformat()
    items = []
    for row in rows:
        published_at = row["published_at"]
        if not published_at.startswith(today_prefix):
            continue
        items.append(dict(row))
    return items
