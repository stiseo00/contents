# 관심사 피드 웹앱 (RSS 기반)

사용자가 선택한 관심사 카테고리로 **오늘 날짜(Asia/Seoul)** 기준의 기사/블로그 글을 RSS로 수집하고, 카드 UI로 보여주는 FastAPI 앱입니다. RSS에 이미지/요약이 없을 때는 OpenGraph(og:image, og:description)로 보강합니다.

## 설치 및 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 동작 흐름

1. `/preferences`에서 관심사 카테고리를 선택
2. `/refresh`로 오늘 글 수집/보강
3. `/`에서 카드 형태로 확인

(선호 설정이 없으면 자동으로 `/preferences`로 리다이렉트됩니다.)

## 주요 구성

- RSS 기본 수집: Google News RSS 검색 (키워드 기반)
- 보강: OG 메타 파싱(og:image, og:description)
- DB: SQLite (`user_prefs`, `feed_items`)
- UI: Jinja2 템플릿 + 다크톤 카드 레이아웃

## 향후 확장 가이드

- 블로그 RSS provider 추가: `app/services/providers.py`에 별도 함수로 RSS URL을 확장하고,
  `fetch_and_enrich()`에서 카테고리별로 병합하면 됩니다.
- 요약 개선: `app/services/summarizer.py`에 LLM 요약 또는 문장 추출을 추가할 수 있습니다.
- 캐시 전략: `feed_items.fetched_at`을 활용해 TTL 기반 재수집 정책을 붙일 수 있습니다.
