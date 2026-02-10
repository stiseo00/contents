# 수집 품질 개선 최종 요약

## 완료된 작업

### 1. 최근 3일 필터 강제 적용 ✅
- 서버에서 `now - 3 days <= publishedAt <= now` 필터 적용
- 한국 시간(Asia/Seoul) 기준 정규화
- publishedAt이 없거나 파싱 실패한 아이템 제외
- 미래 날짜 보정 (now + 10분 초과 시 제외)

### 2. 썸네일 품질 개선 ✅
- og:image 우선 추출
- 동시성 제한 (ThreadPoolExecutor, max_workers=5)
- 이미지가 없는 항목에 대해서만 추출
- 상대 경로를 절대 경로로 변환

### 3. 결과 확장 전략 ✅
- 목표: 최소 10개
- 확장 순서: 페이지네이션 → 추가 키워드 → 다른 소스
- **3일 필터는 절대 깨지지 않음**

### 4. 디버깅 로그 ✅
- 소스별 수집 개수
- 날짜 파싱 성공/실패 개수
- 3일 필터로 drop된 개수
- 이미지 추출 성공률
- 날짜 범위 검증 로그

## 변경된 파일

1. **`real_crawler.py`** (전면 수정)
   - 3일 필터 로직 추가
   - 날짜 파싱 개선 (한국 시간 기준)
   - 이미지 추출 개선 (og:image 우선)
   - 결과 확장 전략 구현
   - 상세 디버깅 로그 추가

2. **`requirements.txt`**
   - `pytz==2024.1` 추가

## 핵심 코드 Diff

### 날짜 필터링
```python
# 추가: 3일 필터 기준 시간 설정
self.now_kst = datetime.now(KST)
self.cutoff_date = self.now_kst - timedelta(days=3)

# 추가: 3일 필터 체크 함수
def is_within_3_days(self, published_at: Optional[datetime]) -> bool:
    if not published_at:
        return False
    # 한국 시간으로 변환 후 필터링
    return self.cutoff_date <= published_at <= self.now_kst
```

### 이미지 추출 개선
```python
# 추가: 동시성 제한 이미지 추출
def enhance_images(self, articles: List[Dict], max_workers: int = 5):
    articles_needing_image = [a for a in articles if not a.get('imageUrl')]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 병렬 처리
```

### 결과 확장 전략
```python
# 수정: 부족하면 확장하되 3일 필터 유지
if len(all_articles) < target_count:
    articles = self.crawl_naver_news(naver_query, max_results=15, start=16)
    # 필터는 crawl_* 함수 내부에서 적용됨
```

## 테스트 결과

### 날짜 범위 검증
```
✅ 모든 기사가 최근 3일 이내: True
- 최신: 2026-02-09T01:47:00+09:00 (0일 9.4시간 전)
- 최구: 2026-02-08T06:20:44+09:00 (1일 4.9시간 전)
```

### 이미지 추출 품질
```
총 기사: 10개
이미지 있음: 10개 (100.0%)
이미지 없음: 0개 (0.0%)
```

### 서버 로그 샘플
```
[구글 뉴스] 날짜 파싱 성공: 15, 실패: 0, 최종 수집: 11개
[3일 필터] 입력: 11개, 날짜 없음 제외: 0개, 과거 제외: 0개, 최종: 11개
[날짜 범위 검증] 모든 날짜가 2026-02-06T11:09:01 이후: True
[이미지 개선] 완료: 10/10개 항목에 이미지 있음 (100.0%)
```

## API 응답 샘플

### 샘플 1: 건강·운동 카테고리
```json
{
  "id": "health_0",
  "title": "추성훈, \"매일 아침 달걀 5개\"… 콩팥 건강 괜찮을까?",
  "url": "https://news.google.com/rss/articles/...",
  "source": "조선일보",
  "publishedAt": "2026-02-09T01:47:00+09:00",
  "imageUrl": "https://...",
  "summary": "..."
}
```

### 샘플 2: 맛집·레시피 카테고리
```json
{
  "id": "food_0",
  "title": "차례상도 바꾼다…사태·갈비·우둔으로 즐기는 색다른 '한우 명절 레시피'",
  "url": "https://news.google.com/rss/articles/...",
  "source": "foodtoda",
  "publishedAt": "2026-02-09T01:30:00+09:00",
  "imageUrl": "https://lh3.googleusercontent.com/...",
  "summary": "..."
}
```

### 샘플 3: IT·앱·AI 트렌드 카테고리
```json
{
  "id": "it_0",
  "title": "AI 기술 동향...",
  "url": "https://news.google.com/rss/articles/...",
  "source": "Google News",
  "publishedAt": "2026-02-09T02:00:00+09:00",
  "imageUrl": "https://...",
  "summary": "..."
}
```

## 검증 완료

- [x] 모든 아이템 publishedAt이 "오늘~3일 전" 범위
- [x] 카드 썸네일이 실제 기사/블로그 대표 이미지로 대부분 채워짐 (100%)
- [x] 부족하면 페이지네이션/키워드 확장으로 10개까지 채우되 과거 글은 0건
- [x] 디버깅 로그로 검증 가능

## 사용 방법

서버가 실행 중입니다. 브라우저에서 http://localhost:8000 접속하여 확인하세요.

### 검증 명령어
```bash
# 날짜 범위 검증
curl "http://localhost:8000/api/news?category=health" | \
  python3 -c "import sys, json; from datetime import datetime, timedelta; import pytz; ..."

# 이미지 품질 검증
curl "http://localhost:8000/api/news?category=food" | \
  python3 -c "import sys, json; ..."

# 서버 로그 확인
tail -f /tmp/news_server.log | grep -E "\[|날짜|필터|이미지"
```
