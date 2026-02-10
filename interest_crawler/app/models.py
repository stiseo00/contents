from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FeedItem:
    id: str
    category: str
    title: str
    url: str
    source: str
    published_at: str
    image_url: str
    summary: str
    fetched_at: str


CATEGORIES: List[Dict[str, object]] = [
    {
        "id": "축구",
        "label": "축구(K리그/EPL/챔스)",
        "keywords": ["K리그", "EPL", "챔피언스리그", "축구"],
    },
    {
        "id": "야구",
        "label": "야구(KBO/MLB)",
        "keywords": ["KBO", "MLB", "야구"],
    },
    {
        "id": "농구",
        "label": "농구(KBL/NBA)",
        "keywords": ["KBL", "NBA", "농구"],
    },
    {
        "id": "배구",
        "label": "배구(V리그)",
        "keywords": ["V리그", "배구"],
    },
    {"id": "골프", "label": "골프", "keywords": ["골프", "PGA", "LPGA"]},
    {"id": "테니스", "label": "테니스", "keywords": ["테니스", "ATP", "WTA"]},
    {"id": "UFC", "label": "UFC", "keywords": ["UFC", "격투기", "MMA"]},
    {
        "id": "e스포츠",
        "label": "e스포츠(LoL)",
        "keywords": ["e스포츠", "LoL", "리그오브레전드", "LCK"],
    },
    {"id": "F1", "label": "F1", "keywords": ["F1", "포뮬러1"]},
    {
        "id": "러닝/마라톤",
        "label": "러닝/마라톤",
        "keywords": ["러닝", "마라톤", "달리기"],
    },
    {
        "id": "등산/아웃도어",
        "label": "등산/아웃도어",
        "keywords": ["등산", "아웃도어", "트레킹"],
    },
    {"id": "IT/테크", "label": "IT/테크", "keywords": ["IT", "테크", "기술"]},
    {"id": "AI", "label": "AI", "keywords": ["AI", "인공지능", "머신러닝"]},
    {
        "id": "스타트업",
        "label": "스타트업",
        "keywords": ["스타트업", "벤처", "창업"],
    },
    {
        "id": "재테크",
        "label": "재테크",
        "keywords": ["재테크", "투자", "자산관리"],
    },
    {"id": "부동산", "label": "부동산", "keywords": ["부동산", "아파트", "주택"]},
    {
        "id": "경제/증시",
        "label": "경제/증시",
        "keywords": ["경제", "증시", "주식", "금리"],
    },
    {
        "id": "건강/운동",
        "label": "건강/운동",
        "keywords": ["건강", "운동", "헬스"]},
    {"id": "다이어트", "label": "다이어트", "keywords": ["다이어트", "체중감량", "식단"]},
    {
        "id": "요리/맛집",
        "label": "요리/맛집",
        "keywords": ["요리", "맛집", "레시피"],
    },
    {"id": "여행", "label": "여행", "keywords": ["여행", "관광", "휴가"]},
    {"id": "자동차", "label": "자동차", "keywords": ["자동차", "전기차", "신차"]},
    {"id": "게임", "label": "게임", "keywords": ["게임", "콘솔", "PC게임"]},
    {"id": "영화", "label": "영화", "keywords": ["영화", "극장", "개봉"]},
    {"id": "드라마", "label": "드라마", "keywords": ["드라마", "OTT", "시리즈"]},
    {"id": "책/독서", "label": "책/독서", "keywords": ["책", "독서", "출판"]},
    {"id": "음악", "label": "음악", "keywords": ["음악", "콘서트", "앨범"]},
    {"id": "교육", "label": "교육", "keywords": ["교육", "학습", "학교"]},
    {"id": "육아", "label": "육아", "keywords": ["육아", "아이", "키즈"]},
    {"id": "반려동물", "label": "반려동물", "keywords": ["반려동물", "강아지", "고양이"]},
    {"id": "패션", "label": "패션", "keywords": ["패션", "스타일", "의류"]},
]


CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    item["id"]: item["keywords"] for item in CATEGORIES
}
