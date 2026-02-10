# 실제 뉴스 수집 구현 완료

## 변경 사항 요약

### 1. 더미 데이터 완전 제거 ✅
- `get_sample_articles()` 함수 제거
- `crawl_category()`에서 샘플 데이터 추가 로직 제거
- 프론트/백엔드에서 `example.com` URL 필터링
- 더미 텍스트("최신 정보 및 팁" 등) 감지 및 필터링

### 2. 실제 소스 크롤러 구현 ✅

#### A. 구글 뉴스 RSS (`crawl_google_news`)
- RSS 피드 기반 수집
- URL: `https://news.google.com/rss/search?q={query}&hl=ko&gl=KR`
- 원문 URL 자동 resolve
- 이미지/요약 추출

#### B. 네이버 뉴스 API (`crawl_naver_news`)
- 공식 검색 API 사용
- 엔드포인트: `/v1/search/news.json`
- 환경변수 필요: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`

#### C. 네이버 블로그 API (`crawl_naver_blog`)
- 공식 검색 API 사용
- 엔드포인트: `/v1/search/blog.json`
- HTML 태그 제거 처리

#### D. 티스토리 RSS (`crawl_tistory_rss`)
- RSS 소스 리스트 기반
- 현재 소스: 브런치, 카카오 테크

### 3. 프론트엔드 개선 ✅
- URL 유효성 검사 (`isValidUrl`)
- 더미 URL 필터링
- 클릭 시 실제 링크로 이동 보장
- 유효하지 않은 URL 시 "원문 링크 없음" 표시

## 환경 설정

### 네이버 API 키 발급
1. https://developers.naver.com/apps/#/register 접속
2. 애플리케이션 등록
3. Client ID, Client Secret 발급

### 환경변수 설정
```bash
export NAVER_CLIENT_ID='your_client_id'
export NAVER_CLIENT_SECRET='your_client_secret'
```

또는 `.env` 파일 사용:
```bash
cp .env.example .env
# .env 파일 편집
```

## 변경된 파일

1. **`real_crawler.py`** (신규)
   - 실제 소스 크롤러 구현
   - 구글 뉴스 RSS
   - 네이버 뉴스/블로그 API
   - 티스토리 RSS

2. **`main.py`**
   - `CategoryCrawler` → `RealNewsCrawler` 변경
   - 더미 URL 필터링 추가
   - 샘플 데이터 제거

3. **`templates/index.html`**
   - URL 유효성 검사 추가
   - 더미 데이터 필터링
   - 클릭 처리 개선

4. **`.env.example`** (신규)
   - 환경변수 예시 파일

## 테스트 방법

### 1. API 직접 테스트
```bash
# 구글 뉴스만 사용 (네이버 API 키 없이도 작동)
curl "http://localhost:8000/api/news?category=health" | jq '.articles[0]'

# 네이버 API 포함 (환경변수 설정 후)
export NAVER_CLIENT_ID='your_id'
export NAVER_CLIENT_SECRET='your_secret'
curl "http://localhost:8000/api/news?category=health" | jq '.articles[0]'
```

### 2. 프론트엔드 테스트
1. 브라우저에서 http://localhost:8000 접속
2. 개발자 도구 콘솔 열기
3. 카테고리 선택
4. 콘솔에서 확인:
   - `[프론트] 수집된 뉴스: N 개`
   - 더미 데이터 필터링 로그
5. 카드 클릭 → 실제 링크로 이동 확인

### 3. 검증 체크리스트
- [ ] 각 카테고리에서 실제 뉴스 10개 이상 반환
- [ ] 모든 카드의 URL이 실제 외부 링크
- [ ] 더미 텍스트("최신 정보 및 팁") 0건
- [ ] 카드 클릭 시 새 탭에서 원문 열림
- [ ] `example.com` URL 없음

## API 응답 예시

```json
{
  "success": true,
  "category": "health",
  "category_name": "건강·운동",
  "count": 12,
  "articles": [
    {
      "id": "health_0",
      "title": "실제 뉴스 제목",
      "url": "https://news.google.com/articles/...",
      "source": "Google News",
      "publishedAt": "2026-02-09T10:00:00",
      "imageUrl": "https://...",
      "summary": "실제 요약 내용..."
    }
  ]
}
```

## 주의사항

1. **네이버 API 키 없이도 작동**
   - 구글 뉴스 RSS만 사용 가능
   - 네이버 API는 선택사항

2. **Rate Limiting**
   - 네이버 API: 일일 호출 제한 있음
   - 구글 뉴스: 제한 없음

3. **캐싱**
   - 카테고리별 5분 캐시
   - 새로고침 시 캐시 무효화

## 향후 개선

1. 비동기 이미지/요약 추출
2. 더 많은 RSS 소스 추가
3. 에러 재시도 로직 강화
4. 부분 실패 시 부분 결과 반환
