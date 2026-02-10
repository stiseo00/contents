# 수집 품질 개선 완료

## 구현된 기능

### 1. 최근 3일 필터 강제 적용 ✅
- 서버에서 `now - 3 days <= publishedAt <= now` 필터 적용
- publishedAt이 없거나 파싱 실패한 아이템 제외
- 한국 시간(Asia/Seoul) 기준으로 정규화
- 미래 날짜 보정 (now + 10분 초과 시 제외)

### 2. 소스별 publishedAt 확보 개선 ✅
- **구글 뉴스 RSS**: `published_parsed` 사용, 파싱 실패 시 제외
- **네이버 뉴스 API**: `pubDate` 파싱, 실패 시 URL에서 추출 시도
- **네이버 블로그 API**: `postdate` (YYYYMMDD) 파싱, 실패 시 URL에서 추출 시도
- **티스토리 RSS**: `published_parsed` 사용

### 3. 썸네일 품질 개선 ✅
- 우선순위:
  1. og:image
  2. twitter:image
  3. link rel="image_src"
  4. 본문 첫 번째 큰 이미지 (200x200 이상)
- 동시성 제한 (ThreadPoolExecutor, max_workers=5)
- 상대 경로를 절대 경로로 변환
- 이미지가 없는 항목에 대해서만 추출 (불필요 요청 최소화)

### 4. 결과 확장 전략 ✅
- 목표: 최소 10개
- 확장 순서:
  1. 같은 소스에서 페이지네이션 확장
  2. 추가 키워드로 검색 확대
  3. 다른 소스 추가
- **중요**: 3일 필터는 절대 깨지지 않음

### 5. 디버깅 로그 ✅
- 소스별 수집 개수
- publishedAt 파싱 성공/실패 개수
- 3일 필터로 drop된 개수
- 최종 반환 개수
- 이미지 URL 추출 성공률
- 날짜 범위 검증 로그

## 변경된 파일

### `real_crawler.py` (전면 수정)
- 3일 필터 로직 추가
- 날짜 파싱 개선 (한국 시간 기준)
- 이미지 추출 개선 (og:image 우선, 동시성 제한)
- 결과 확장 전략 구현
- 상세 디버깅 로그 추가

### `requirements.txt`
- `pytz==2024.1` 추가 (시간대 지원)

## 핵심 코드

### 1. 3일 필터 적용
```python
def is_within_3_days(self, published_at: Optional[datetime]) -> bool:
    if not published_at:
        return False
    
    # 한국 시간으로 변환
    if published_at.tzinfo is None:
        published_at = KST.localize(published_at)
    else:
        published_at = published_at.astimezone(KST)
    
    # 미래 날짜 체크
    if published_at > self.max_future_date:
        return False
    
    # 3일 필터 체크
    return self.cutoff_date <= published_at <= self.now_kst
```

### 2. 이미지 추출 개선
```python
def enhance_images(self, articles: List[Dict], max_workers: int = 5):
    # 이미지가 없는 항목만 추출
    articles_needing_image = [a for a in articles if not a.get('imageUrl')]
    
    # 동시성 제한으로 추출
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 병렬 처리
```

### 3. 결과 확장 전략
```python
# 부족하면 페이지네이션 확장
if len(all_articles) < target_count:
    articles = self.crawl_naver_news(naver_query, max_results=15, start=16)
    all_articles.extend(articles)

# 부족하면 추가 키워드로 확장
if len(all_articles) < target_count:
    for keyword in keywords[1:3]:
        articles = self.crawl_google_news(keyword, max_results=10)
        all_articles.extend(articles)
```

## 테스트 결과

### 날짜 범위 검증
```
현재 시간: 2026-02-09T10:57:00+09:00
기준 시간 (3일 전): 2026-02-06T10:57:00+09:00

✅ 모든 기사가 최근 3일 이내: True
```

### 이미지 추출 품질
```
총 기사: 11개
이미지 있음: 8개 (72.7%)
이미지 없음: 3개 (27.3%)
```

## 검증 방법

### 1. 날짜 범위 검증
```bash
curl "http://localhost:8000/api/news?category=health" | \
  python3 -c "import sys, json; from datetime import datetime, timedelta; import pytz; ..."
```

### 2. 이미지 품질 검증
```bash
curl "http://localhost:8000/api/news?category=food" | \
  python3 -c "import sys, json; ..."
```

### 3. 서버 로그 확인
```bash
tail -f /tmp/news_server.log | grep -E "\[|날짜|필터|이미지"
```

## 완료 조건

- [x] 모든 아이템 publishedAt이 "오늘~3일 전" 범위
- [x] 카드 썸네일이 실제 기사/블로그 대표 이미지로 대부분 채워짐
- [x] 부족하면 페이지네이션/키워드 확장으로 10개까지 채우되 과거 글은 0건
- [x] 디버깅 로그로 검증 가능
