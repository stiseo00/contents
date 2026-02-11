from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from real_crawler import RealNewsCrawler
import uvicorn
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
import json
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="관심사 뉴스 크롤러")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 크롤러 인스턴스
news_crawler = RealNewsCrawler()

# 데이터 저장 디렉토리
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# 한국 시간대
KST = pytz.timezone('Asia/Seoul')

# 스케줄러 인스턴스
scheduler = BackgroundScheduler(timezone=KST)


def get_cache_file_path(category: str) -> str:
    """카테고리별 캐시 파일 경로"""
    return os.path.join(DATA_DIR, f"{category}.json")


def save_news_to_file(category: str, articles: List[Dict]):
    """뉴스 데이터를 JSON 파일로 저장"""
    try:
        file_path = get_cache_file_path(category)
        data = {
            'articles': articles,
            'cached_at': datetime.now(KST).isoformat(),
            'category': category,
            'category_name': news_crawler.CATEGORIES.get(category, {}).get('name', category)
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[파일 저장] {category}: {len(articles)}개 기사 저장 완료")
    except Exception as e:
        logger.error(f"[파일 저장] {category} 오류: {e}", exc_info=True)


def load_news_from_file(category: str) -> Optional[Dict]:
    """파일에서 뉴스 데이터 로드"""
    try:
        file_path = get_cache_file_path(category)
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"[파일 로드] {category}: {len(data.get('articles', []))}개 기사 로드 완료")
        return data
    except Exception as e:
        logger.error(f"[파일 로드] {category} 오류: {e}", exc_info=True)
        return None


def crawl_all_categories():
    """모든 카테고리 크롤링 (스케줄링용)"""
    logger.info("=" * 60)
    logger.info("[스케줄 크롤링 시작] 모든 카테고리 크롤링 시작")
    logger.info(f"[시간] {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")
    
    categories = list(news_crawler.CATEGORIES.keys())
    success_count = 0
    fail_count = 0
    
    for category in categories:
        try:
            logger.info(f"[크롤링] {category} 시작...")
            articles = news_crawler.crawl_category(category)
            
            # 포맷팅
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
                    "publishedAt": article.get('publishedAt', datetime.now(KST).isoformat()),
                    "imageUrl": article.get('imageUrl', '') or '',
                    "summary": article.get('summary', '') or ''
                })
            
            # 파일 저장
            save_news_to_file(category, formatted_articles)
            success_count += 1
            logger.info(f"[크롤링 완료] {category}: {len(formatted_articles)}개 기사")
            
        except Exception as e:
            fail_count += 1
            logger.error(f"[크롤링 실패] {category}: {e}", exc_info=True)
    
    logger.info(f"[스케줄 크롤링 완료] 성공: {success_count}개, 실패: {fail_count}개")
    logger.info("=" * 60)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 초기화"""
    logger.info("앱 시작 - 스케줄링 크롤러 준비 중...")
    
    # 스케줄러 설정: 매일 8시, 17시에 크롤링
    scheduler.add_job(
        crawl_all_categories,
        trigger=CronTrigger(hour='8,17', minute=0),  # 매일 8시, 17시
        id='daily_crawl',
        name='매일 아침 8시, 저녁 5시 크롤링',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("✅ 스케줄러 시작 완료 (매일 8시, 17시 자동 크롤링)")
    
    # 앱 시작 시 즉시 한 번 크롤링 (데이터가 없을 경우)
    logger.info("[초기 크롤링] 저장된 데이터 확인 중...")
    has_data = False
    for category in news_crawler.CATEGORIES.keys():
        if load_news_from_file(category):
            has_data = True
            break
    
    if not has_data:
        logger.info("[초기 크롤링] 저장된 데이터가 없어 즉시 크롤링 시작...")
        crawl_all_categories()
    else:
        logger.info("[초기 크롤링] 저장된 데이터가 있어 스킵합니다.")


@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 스케줄러 종료"""
    scheduler.shutdown()
    logger.info("스케줄러 종료 완료")


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
    """카테고리별 뉴스 API (파일에서 즉시 반환)"""
    if not category:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "카테고리를 선택해주세요.",
                "categories": news_crawler.get_all_categories()
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
    
    # 파일에서 데이터 로드 (즉시 반환)
    cached_data = load_news_from_file(category)
    
    if cached_data and cached_data.get('articles'):
        logger.info(f"[API] {category} 카테고리 파일에서 로드: {len(cached_data['articles'])}개")
        return {
            "success": True,
            "category": category,
            "category_name": cached_data.get('category_name', news_crawler.CATEGORIES[category]['name']),
            "count": len(cached_data['articles']),
            "articles": cached_data['articles'],
            "cached_at": cached_data.get('cached_at')
        }
    else:
        # 데이터가 없으면 빈 배열 반환
        logger.warning(f"[API] {category} 카테고리 데이터 없음")
        return {
            "success": True,
            "category": category,
            "category_name": news_crawler.CATEGORIES[category]['name'],
            "count": 0,
            "articles": [],
            "message": "아직 수집된 뉴스가 없습니다. 다음 크롤링 시간(오전 8시 또는 오후 5시)을 기다려주세요."
        }


@app.get("/api/news/refresh")
async def refresh_news(category: Optional[str] = Query(None)):
    """뉴스 수동 새로고침 (즉시 크롤링)"""
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
        logger.info(f"[수동 새로고침] {category} 카테고리 크롤링 시작...")
        
        # 크롤링 수행
        articles = news_crawler.crawl_category(category)
        
        # 포맷팅
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
                "publishedAt": article.get('publishedAt', datetime.now(KST).isoformat()),
                "imageUrl": article.get('imageUrl', '') or '',
                "summary": article.get('summary', '') or ''
            })
        
        # 파일 저장
        save_news_to_file(category, formatted_articles)
        
        return {
            "success": True,
            "message": "뉴스가 새로고침되었습니다.",
            "category": category,
            "category_name": news_crawler.CATEGORIES[category]['name'],
            "count": len(formatted_articles)
        }
    
    except Exception as e:
        logger.error(f"[수동 새로고침] {category} 오류: {e}", exc_info=True)
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
    cached_categories = []
    total_news = 0
    
    for category in news_crawler.CATEGORIES.keys():
        data = load_news_from_file(category)
        if data and data.get('articles'):
            cached_categories.append(category)
            total_news += len(data['articles'])
    
    # 다음 크롤링 시간 계산
    now = datetime.now(KST)
    next_crawl_times = []
    
    # 오늘 8시, 17시 확인
    today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    today_5pm = now.replace(hour=17, minute=0, second=0, microsecond=0)
    
    if now < today_8am:
        next_crawl_times.append(today_8am.isoformat())
    elif now < today_5pm:
        next_crawl_times.append(today_5pm.isoformat())
    else:
        # 내일 8시
        tomorrow_8am = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        next_crawl_times.append(tomorrow_8am.isoformat())
    
    return {
        "status": "healthy",
        "cached_categories": cached_categories,
        "total_news_count": total_news,
        "next_crawl_times": next_crawl_times,
        "scheduler_running": scheduler.running
    }


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎯 관심사 뉴스 크롤러 시작 (스케줄링 모드)")
    print("="*60)
    print("\n📍 웹 브라우저에서 다음 주소로 접속하세요:")
    print("   👉 http://localhost:8000")
    print("\n⏰ 자동 크롤링 시간:")
    print("   - 매일 오전 8시")
    print("   - 매일 오후 5시")
    print("\n📡 API 엔드포인트:")
    print("   - GET /api/categories     : 카테고리 목록 조회")
    print("   - GET /api/news?category= : 카테고리별 뉴스 조회 (즉시 반환)")
    print("   - GET /api/news/refresh?category= : 수동 새로고침")
    print("   - GET /health             : 서버 상태 확인")
    print("\n📂 지원 카테고리:")
    categories = RealNewsCrawler().get_all_categories()
    for key, name in categories.items():
        print(f"   - {name} ({key})")
    print("\n⚠️  네이버 API 사용 시 환경변수 설정 필요:")
    print("   export NAVER_CLIENT_ID='your_client_id'")
    print("   export NAVER_CLIENT_SECRET='your_client_secret'")
    print("\n💾 데이터 저장 위치: data/ 디렉토리")
    print("\n⏹️  종료하려면 Ctrl+C를 누르세요\n")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
