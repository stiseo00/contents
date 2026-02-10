from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from real_crawler import RealNewsCrawler
import uvicorn
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="관심사 뉴스 크롤러")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 크롤러 인스턴스 (실제 소스 사용)
news_crawler = RealNewsCrawler()

# 캐시된 뉴스 데이터 (카테고리별)
cached_news: Dict[str, Dict] = {}  # {category: {'articles': [...], 'cached_at': datetime}}

# 캐시 TTL (5분)
CACHE_TTL = timedelta(minutes=5)


def is_cache_valid(category: str) -> bool:
    """캐시가 유효한지 확인"""
    if category not in cached_news:
        return False
    
    cached_at = cached_news[category].get('cached_at')
    if not cached_at:
        return False
    
    if isinstance(cached_at, str):
        cached_at = datetime.fromisoformat(cached_at)
    
    return datetime.now() - cached_at < CACHE_TTL


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 초기화"""
    logger.info("앱 시작 - 카테고리 크롤러 준비 완료")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, category: Optional[str] = Query(None)):
    """메인 페이지"""
    categories = news_crawler.get_all_categories()
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "categories": categories,
            "current_category": category
        }
    )


@app.get("/api/categories")
async def get_categories():
    """카테고리 목록 API"""
    categories = news_crawler.get_all_categories()
    return {
        "success": True,
        "categories": categories
    }


@app.get("/api/news")
async def get_news(category: Optional[str] = Query(None)):
    """카테고리별 뉴스 API (개선)"""
    if not category:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "카테고리를 선택해주세요.",
                "categories": category_crawler.get_all_categories()
            }
        )
    
    if category not in news_crawler.CATEGORIES:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"알 수 없는 카테고리: {category}"
            }
        )
    
    # 캐시 확인
    if is_cache_valid(category):
        logger.info(f"[API] {category} 카테고리 캐시 사용")
        return {
            "success": True,
            "category": category,
            "category_name": news_crawler.CATEGORIES[category]['name'],
            "count": len(cached_news[category]['articles']),
            "articles": cached_news[category]['articles']
        }
    
    # 크롤링 수행
    try:
        logger.info(f"[API] {category} 카테고리 크롤링 시작...")
        logger.info(f"[API] 카테고리 정보: {news_crawler.CATEGORIES.get(category, 'NOT FOUND')}")
        
        articles = news_crawler.crawl_category(category)
        logger.info(f"[API] 크롤링 결과: {len(articles)}개 기사")
        
        # 응답 형식 통일 (실제 데이터만 반환, 샘플 데이터 없음)
        formatted_articles = []
        for i, article in enumerate(articles):
            url = article.get('url', '')
            # 더미 URL 필터링
            if 'example.com' in url or not url or url.startswith('https://example'):
                logger.warning(f"[API] 더미 URL 필터링: {url}")
                continue
            
            formatted_articles.append({
                "id": f"{category}_{i}",
                "title": article.get('title', ''),
                "url": url,
                "source": article.get('source', ''),
                "publishedAt": article.get('publishedAt', datetime.now().isoformat()),
                "imageUrl": article.get('imageUrl', '') or '',
                "summary": article.get('summary', '') or ''
            })
        
        logger.info(f"[API] 포맷팅 완료: {len(formatted_articles)}개 (더미 필터링 후)")
        
        # 캐시 저장
        cached_news[category] = {
            'articles': formatted_articles,
            'cached_at': datetime.now()
        }
        
        return {
            "success": True,
            "category": category,
            "category_name": news_crawler.CATEGORIES[category]['name'],
            "count": len(formatted_articles),
            "articles": formatted_articles
        }
    
    except Exception as e:
        logger.error(f"[API] {category} 카테고리 크롤링 오류: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"뉴스를 불러오는 중 오류가 발생했습니다: {str(e)}",
                "articles": []
            }
        )


@app.get("/api/news/refresh")
async def refresh_news(category: Optional[str] = Query(None)):
    """뉴스 새로고침"""
    if not category:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "카테고리를 선택해주세요."
            }
        )
    
    if category not in news_crawler.CATEGORIES:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"알 수 없는 카테고리: {category}"
            }
        )
    
    try:
        logger.info(f"[API] {category} 카테고리 뉴스 새로고침 요청...")
        
        # 캐시 무효화
        if category in cached_news:
            del cached_news[category]
        
        # 크롤링 수행
        articles = news_crawler.crawl_category(category)
        
        # 응답 형식 통일 (더미 URL 필터링)
        formatted_articles = []
        for i, article in enumerate(articles):
            url = article.get('url', '')
            if 'example.com' in url or not url or url.startswith('https://example'):
                continue
            
            formatted_articles.append({
                "id": f"{category}_{i}",
                "title": article.get('title', ''),
                "url": url,
                "source": article.get('source', ''),
                "publishedAt": article.get('publishedAt', datetime.now().isoformat()),
                "imageUrl": article.get('imageUrl', '') or '',
                "summary": article.get('summary', '') or ''
            })
        
        # 캐시 저장
        cached_news[category] = {
            'articles': formatted_articles,
            'cached_at': datetime.now()
        }
        
        return {
            "success": True,
            "message": "뉴스가 새로고침되었습니다.",
            "category": category,
            "category_name": news_crawler.CATEGORIES[category]['name'],
            "count": len(formatted_articles)
        }
    
    except Exception as e:
        logger.error(f"{category} 카테고리 새로고침 오류: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"새로고침 중 오류가 발생했습니다: {str(e)}"
            }
        )


@app.get("/health")
async def health_check():
    """헬스 체크"""
    total_news = sum(len(data.get('articles', [])) for data in cached_news.values())
    return {
        "status": "healthy",
        "cached_categories": list(cached_news.keys()),
        "total_news_count": total_news,
        "cache_ttl_minutes": CACHE_TTL.total_seconds() / 60
    }


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎯 관심사 뉴스 크롤러 시작")
    print("="*60)
    print("\n📍 웹 브라우저에서 다음 주소로 접속하세요:")
    print("   👉 http://localhost:8000")
    print("\n📡 API 엔드포인트:")
    print("   - GET /api/categories     : 카테고리 목록 조회")
    print("   - GET /api/news?category= : 카테고리별 뉴스 조회")
    print("   - GET /api/news/refresh?category= : 뉴스 새로고침")
    print("\n📂 지원 카테고리:")
    categories = RealNewsCrawler().get_all_categories()
    for key, name in categories.items():
        print(f"   - {name} ({key})")
    print("\n⚠️  네이버 API 사용 시 환경변수 설정 필요:")
    print("   export NAVER_CLIENT_ID='your_client_id'")
    print("   export NAVER_CLIENT_SECRET='your_client_secret'")
    print("\n⏹️  종료하려면 Ctrl+C를 누르세요\n")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
