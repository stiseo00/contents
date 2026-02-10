import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import re
import feedparser
import logging
from urllib.parse import urlparse, urljoin, urlunparse, quote, parse_qs
import time
from difflib import SequenceMatcher
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 한국 시간대
KST = pytz.timezone('Asia/Seoul')


class RealNewsCrawler:
    """실제 뉴스/블로그 소스에서 수집하는 크롤러 (3일 필터 + 썸네일 개선)"""
    
    # 카테고리 정의 (slug 기반)
    CATEGORIES = {
        'health': {
            'name': '건강·운동',
            'keywords': ['건강', '운동', '다이어트', '헬스', '요가', '필라테스'],
            'google_query': '건강 운동 OR 다이어트 OR 헬스',
            'naver_query': '건강 운동'
        },
        'food': {
            'name': '맛집·레시피',
            'keywords': ['맛집', '레시피', '요리', '혼밥', '카페'],
            'google_query': '맛집 레시피 OR 요리',
            'naver_query': '맛집 레시피'
        },
        'finance': {
            'name': '재테크·돈관리',
            'keywords': ['재테크', '투자', '주식', '가계부', '절약'],
            'google_query': '재테크 투자 OR 주식',
            'naver_query': '재테크 투자'
        },
        'travel': {
            'name': '여행·주말나들이',
            'keywords': ['여행', '주말', '당일치기', '여행지', '명소'],
            'google_query': '여행 주말 OR 당일치기',
            'naver_query': '여행 주말'
        },
        'relationship': {
            'name': '연애·관계·심리',
            'keywords': ['연애', '심리', '관계', 'MBTI', '대화법'],
            'google_query': '연애 심리 OR 관계',
            'naver_query': '연애 심리'
        },
        'self_improvement': {
            'name': '자기계발·공부법',
            'keywords': ['자기계발', '공부법', '시간관리', '독서'],
            'google_query': '자기계발 공부법 OR 시간관리',
            'naver_query': '자기계발 공부법'
        },
        'it': {
            'name': 'IT·앱·AI 트렌드',
            'keywords': ['IT', '앱', 'AI', '기술', '스마트폰'],
            'google_query': 'IT AI OR 앱 OR 기술',
            'naver_query': 'IT AI'
        },
        'beauty': {
            'name': '뷰티·패션·그루밍',
            'keywords': ['뷰티', '패션', '스킨케어', '화장품'],
            'google_query': '뷰티 패션 OR 스킨케어',
            'naver_query': '뷰티 패션'
        },
        'home': {
            'name': '집·인테리어·살림',
            'keywords': ['인테리어', '집꾸미기', '정리정돈', '청소'],
            'google_query': '인테리어 집꾸미기 OR 정리정돈',
            'naver_query': '인테리어 집꾸미기'
        },
        'hobby': {
            'name': '취미·문화생활',
            'keywords': ['영화', '드라마', '전시', '음악', '취미'],
            'google_query': '영화 드라마 OR 전시 OR 음악',
            'naver_query': '영화 드라마'
        },
        'family': {
            'name': '육아·가족·반려동물',
            'keywords': ['육아', '아이', '반려동물', '강아지', '고양이'],
            'google_query': '육아 반려동물 OR 강아지',
            'naver_query': '육아 반려동물'
        },
        'sports': {
            'name': '스포츠',
            'keywords': ['스포츠', '축구', '야구', '농구', '배구'],
            'google_query': '스포츠 축구 OR 야구 OR 농구',
            'naver_query': '스포츠 축구'
        }
    }
    
    # 티스토리 RSS 소스 리스트
    TISTORY_RSS_SOURCES = [
        'https://brunch.co.kr/rss',
        'https://tech.kakao.com/feed/',
    ]
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 네이버 API 키
        self.naver_client_id = os.getenv('NAVER_CLIENT_ID', '')
        self.naver_client_secret = os.getenv('NAVER_CLIENT_SECRET', '')
        
        # 3일 필터 기준 시간
        self.now_kst = datetime.now(KST)
        self.cutoff_date = self.now_kst - timedelta(days=3)
        self.max_future_date = self.now_kst + timedelta(minutes=10)  # 미래 날짜 보정용
        
        logger.info(f"[시간 필터] 현재: {self.now_kst.isoformat()}, 기준: {self.cutoff_date.isoformat()} (최근 3일)")
    
    def normalize_url(self, url: str) -> str:
        """URL 정규화"""
        try:
            parsed = urlparse(url)
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path.rstrip('/'),
                parsed.params,
                '',
                ''
            ))
            return normalized
        except Exception:
            return url
    
    def parse_published_date(self, date_str: str, url: str = '') -> Optional[datetime]:
        """날짜 파싱 (한국 시간 기준)"""
        if not date_str:
            return None
        
        try:
            # ISO 형식
            if 'T' in date_str or '+' in date_str or 'Z' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = KST.localize(dt)
                else:
                    dt = dt.astimezone(KST)
                return dt
            
            # RFC 2822 형식 (RSS)
            try:
                dt = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
                return dt.astimezone(KST)
            except:
                pass
            
            # YYYYMMDD 형식 (네이버 블로그)
            if len(date_str) == 8 and date_str.isdigit():
                dt = datetime.strptime(date_str, '%Y%m%d')
                return KST.localize(dt)
            
            # 기타 형식 시도
            patterns = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%Y.%m.%d',
            ]
            
            for pattern in patterns:
                try:
                    dt = datetime.strptime(date_str[:19], pattern)
                    return KST.localize(dt)
                except:
                    continue
            
            return None
        
        except Exception as e:
            logger.debug(f"[날짜 파싱 실패] {date_str[:50]}: {e}")
            return None
    
    def fetch_published_date_from_url(self, url: str) -> Optional[datetime]:
        """URL에서 publishedAt 추출"""
        try:
            response = self.session.get(url, timeout=5, allow_redirects=True)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # og:published_time
            og_date = soup.select_one('meta[property="article:published_time"]')
            if og_date and og_date.get('content'):
                dt = self.parse_published_date(og_date.get('content'))
                if dt:
                    return dt
            
            # time 태그
            time_tag = soup.select_one('time[datetime]')
            if time_tag:
                dt = self.parse_published_date(time_tag.get('datetime'))
                if dt:
                    return dt
            
            return None
        
        except Exception as e:
            logger.debug(f"[URL 날짜 추출 실패] {url}: {e}")
            return None
    
    def is_within_3_days(self, published_at: Optional[datetime]) -> bool:
        """3일 필터 체크"""
        if not published_at:
            return False
        
        # 한국 시간으로 변환
        if published_at.tzinfo is None:
            published_at = KST.localize(published_at)
        else:
            published_at = published_at.astimezone(KST)
        
        # 미래 날짜 체크 (보정)
        if published_at > self.max_future_date:
            logger.debug(f"[미래 날짜 보정] {published_at.isoformat()} → {self.now_kst.isoformat()}")
            return False
        
        # 3일 필터 체크
        is_valid = self.cutoff_date <= published_at <= self.now_kst
        if not is_valid:
            logger.debug(f"[3일 필터 제외] {published_at.isoformat()} (기준: {self.cutoff_date.isoformat()})")
        
        return is_valid
    
    def extract_image_from_url(self, url: str) -> Optional[str]:
        """URL에서 이미지 추출 (og:image 우선)"""
        try:
            response = self.session.get(url, timeout=5, allow_redirects=True)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. og:image
            og_image = soup.select_one('meta[property="og:image"]')
            if og_image and og_image.get('content'):
                img_url = og_image.get('content')
                return self.normalize_image_url(img_url, url)
            
            # 2. twitter:image
            twitter_image = soup.select_one('meta[name="twitter:image"]')
            if twitter_image and twitter_image.get('content'):
                img_url = twitter_image.get('content')
                return self.normalize_image_url(img_url, url)
            
            # 3. link rel="image_src"
            link_image = soup.select_one('link[rel="image_src"]')
            if link_image and link_image.get('href'):
                img_url = link_image.get('href')
                return self.normalize_image_url(img_url, url)
            
            # 4. 본문 첫 번째 큰 이미지
            article_images = soup.select('article img, .post-content img, .entry-content img')
            for img in article_images[:5]:
                src = img.get('src') or img.get('data-src')
                if src:
                    # 큰 이미지 필터링 (너비/높이 속성 체크)
                    width = img.get('width', '')
                    height = img.get('height', '')
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w >= 200 and h >= 200:
                                return self.normalize_image_url(src, url)
                        except:
                            pass
                    # 속성이 없어도 시도
                    return self.normalize_image_url(src, url)
            
            return None
        
        except Exception as e:
            logger.debug(f"[이미지 추출 실패] {url}: {e}")
            return None
    
    def normalize_image_url(self, img_url: str, base_url: str) -> str:
        """이미지 URL 정규화"""
        if not img_url:
            return ''
        
        if img_url.startswith('http://') or img_url.startswith('https://'):
            return img_url
        elif img_url.startswith('//'):
            return 'https:' + img_url
        elif img_url.startswith('/'):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{img_url}"
        else:
            return urljoin(base_url, img_url)
    
    def resolve_google_news_url(self, google_url: str) -> str:
        """구글 뉴스 URL을 원문 URL로 변환"""
        try:
            response = self.session.head(google_url, allow_redirects=True, timeout=5)
            final_url = response.url
            
            if 'news.google.com' in final_url:
                parsed = urlparse(final_url)
                if parsed.query:
                    params = parse_qs(parsed.query)
                    if 'url' in params:
                        return params['url'][0]
            
            return final_url
        except Exception as e:
            logger.debug(f"URL resolve 실패: {e}")
            return google_url
    
    def crawl_google_news(self, query: str, max_results: int = 15, page: int = 1) -> List[Dict]:
        """구글 뉴스 RSS 크롤링"""
        articles = []
        parse_success = 0
        parse_failed = 0
        
        try:
            logger.info(f"[구글 뉴스] 쿼리: {query}, 최대 {max_results}개, 페이지 {page}")
            rss_url = f'https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko'
            
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                logger.warning(f"[구글 뉴스] RSS 피드가 비어있습니다")
                return articles
            
            logger.info(f"[구글 뉴스] 발견된 항목: {len(feed.entries)}개")
            
            for entry in feed.entries[:max_results]:
                try:
                    title = entry.get('title', '').strip()
                    link = entry.get('link', '')
                    
                    if not title or not link:
                        continue
                    
                    # 원문 URL resolve
                    original_url = self.resolve_google_news_url(link)
                    
                    # 날짜 파싱
                    published_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            dt = datetime(*entry.published_parsed[:6])
                            published_at = KST.localize(dt)
                            parse_success += 1
                        except Exception as e:
                            logger.debug(f"[구글 뉴스] 날짜 파싱 실패: {e}")
                            parse_failed += 1
                            continue
                    else:
                        parse_failed += 1
                        continue
                    
                    # 3일 필터 체크
                    if not self.is_within_3_days(published_at):
                        continue
                    
                    # 이미지 추출
                    image_url = None
                    if 'media_content' in entry:
                        image_url = entry.media_content[0].get('url', '')
                    
                    # og:image 추출 시도
                    if not image_url:
                        image_url = self.extract_image_from_url(original_url)
                    
                    # 요약 (HTML 태그 제거)
                    summary = entry.get('summary', '')
                    if summary:
                        summary = BeautifulSoup(summary, 'html.parser').get_text(strip=True)[:200]
                    else:
                        summary = None
                    
                    articles.append({
                        'title': title,
                        'url': original_url,
                        'source': entry.get('source', {}).get('title', 'Google News'),
                        'publishedAt': published_at.isoformat(),
                        'imageUrl': image_url or '',
                        'summary': summary or ''
                    })
                    
                    logger.debug(f"[구글 뉴스] 수집: {title[:50]}... ({published_at.isoformat()})")
                
                except Exception as e:
                    logger.error(f"[구글 뉴스] 항목 파싱 오류: {e}")
                    continue
            
            logger.info(f"[구글 뉴스] 날짜 파싱 성공: {parse_success}, 실패: {parse_failed}, 최종 수집: {len(articles)}개")
        
        except Exception as e:
            logger.error(f"[구글 뉴스] 크롤링 오류: {e}", exc_info=True)
        
        return articles
    
    def crawl_naver_news(self, query: str, max_results: int = 15, start: int = 1) -> List[Dict]:
        """네이버 뉴스 API 크롤링"""
        articles = []
        parse_success = 0
        parse_failed = 0
        
        if not self.naver_client_id or not self.naver_client_secret:
            logger.warning("[네이버 뉴스] API 키가 설정되지 않았습니다")
            return articles
        
        try:
            logger.info(f"[네이버 뉴스] 쿼리: {query}, 최대 {max_results}개, 시작: {start}")
            url = 'https://openapi.naver.com/v1/search/news.json'
            headers = {
                'X-Naver-Client-Id': self.naver_client_id,
                'X-Naver-Client-Secret': self.naver_client_secret
            }
            params = {
                'query': query,
                'display': min(max_results, 100),
                'start': start,
                'sort': 'date'
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"[네이버 뉴스] API 오류: {response.status_code}")
                return articles
            
            data = response.json()
            items = data.get('items', [])
            
            logger.info(f"[네이버 뉴스] 발견된 항목: {len(items)}개")
            
            for item in items:
                try:
                    title = BeautifulSoup(item.get('title', ''), 'html.parser').get_text(strip=True)
                    link = item.get('link', '')
                    description = BeautifulSoup(item.get('description', ''), 'html.parser').get_text(strip=True)
                    pub_date = item.get('pubDate', '')
                    
                    if not title or not link:
                        continue
                    
                    # 날짜 파싱
                    published_at = self.parse_published_date(pub_date, link)
                    
                    if not published_at:
                        # URL에서 날짜 추출 시도
                        published_at = self.fetch_published_date_from_url(link)
                    
                    if not published_at:
                        parse_failed += 1
                        logger.debug(f"[네이버 뉴스] 날짜 파싱 실패: {title[:30]}...")
                        continue
                    
                    parse_success += 1
                    
                    # 3일 필터 체크
                    if not self.is_within_3_days(published_at):
                        continue
                    
                    # 이미지 추출
                    image_url = item.get('thumbnail', '') or ''
                    if not image_url:
                        image_url = self.extract_image_from_url(link)
                    
                    articles.append({
                        'title': title,
                        'url': link,
                        'source': 'Naver News',
                        'publishedAt': published_at.isoformat(),
                        'imageUrl': image_url or '',
                        'summary': description[:200] if description else ''
                    })
                    
                    logger.debug(f"[네이버 뉴스] 수집: {title[:50]}... ({published_at.isoformat()})")
                
                except Exception as e:
                    logger.error(f"[네이버 뉴스] 항목 파싱 오류: {e}")
                    continue
            
            logger.info(f"[네이버 뉴스] 날짜 파싱 성공: {parse_success}, 실패: {parse_failed}, 최종 수집: {len(articles)}개")
        
        except Exception as e:
            logger.error(f"[네이버 뉴스] 크롤링 오류: {e}", exc_info=True)
        
        return articles
    
    def crawl_naver_blog(self, query: str, max_results: int = 15, start: int = 1) -> List[Dict]:
        """네이버 블로그 API 크롤링"""
        articles = []
        parse_success = 0
        parse_failed = 0
        
        if not self.naver_client_id or not self.naver_client_secret:
            logger.warning("[네이버 블로그] API 키가 설정되지 않았습니다")
            return articles
        
        try:
            logger.info(f"[네이버 블로그] 쿼리: {query}, 최대 {max_results}개, 시작: {start}")
            url = 'https://openapi.naver.com/v1/search/blog.json'
            headers = {
                'X-Naver-Client-Id': self.naver_client_id,
                'X-Naver-Client-Secret': self.naver_client_secret
            }
            params = {
                'query': query,
                'display': min(max_results, 100),
                'start': start,
                'sort': 'date'
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"[네이버 블로그] API 오류: {response.status_code}")
                return articles
            
            data = response.json()
            items = data.get('items', [])
            
            logger.info(f"[네이버 블로그] 발견된 항목: {len(items)}개")
            
            for item in items:
                try:
                    title = BeautifulSoup(item.get('title', ''), 'html.parser').get_text(strip=True)
                    link = item.get('link', '')
                    description = BeautifulSoup(item.get('description', ''), 'html.parser').get_text(strip=True)
                    bloggername = item.get('bloggername', '')
                    postdate = item.get('postdate', '')
                    
                    if not title or not link:
                        continue
                    
                    # 날짜 파싱 (YYYYMMDD 형식)
                    published_at = self.parse_published_date(postdate, link)
                    
                    if not published_at:
                        # URL에서 날짜 추출 시도
                        published_at = self.fetch_published_date_from_url(link)
                    
                    if not published_at:
                        parse_failed += 1
                        logger.debug(f"[네이버 블로그] 날짜 파싱 실패: {title[:30]}...")
                        continue
                    
                    parse_success += 1
                    
                    # 3일 필터 체크
                    if not self.is_within_3_days(published_at):
                        continue
                    
                    # 이미지 추출
                    image_url = self.extract_image_from_url(link)
                    
                    articles.append({
                        'title': title,
                        'url': link,
                        'source': f'Naver Blog ({bloggername})' if bloggername else 'Naver Blog',
                        'publishedAt': published_at.isoformat(),
                        'imageUrl': image_url or '',
                        'summary': description[:200] if description else ''
                    })
                    
                    logger.debug(f"[네이버 블로그] 수집: {title[:50]}... ({published_at.isoformat()})")
                
                except Exception as e:
                    logger.error(f"[네이버 블로그] 항목 파싱 오류: {e}")
                    continue
            
            logger.info(f"[네이버 블로그] 날짜 파싱 성공: {parse_success}, 실패: {parse_failed}, 최종 수집: {len(articles)}개")
        
        except Exception as e:
            logger.error(f"[네이버 블로그] 크롤링 오류: {e}", exc_info=True)
        
        return articles
    
    def crawl_tistory_rss(self, max_results: int = 10) -> List[Dict]:
        """티스토리 RSS 소스 크롤링"""
        articles = []
        parse_success = 0
        parse_failed = 0
        
        for rss_url in self.TISTORY_RSS_SOURCES:
            try:
                logger.info(f"[티스토리 RSS] 소스: {rss_url}")
                feed = feedparser.parse(rss_url)
                
                if not feed.entries:
                    logger.warning(f"[티스토리 RSS] 피드가 비어있습니다: {rss_url}")
                    continue
                
                for entry in feed.entries[:max_results]:
                    try:
                        title = entry.get('title', '').strip()
                        link = entry.get('link', '')
                        
                        if not title or not link:
                            continue
                        
                        # 날짜 파싱
                        published_at = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            try:
                                dt = datetime(*entry.published_parsed[:6])
                                published_at = KST.localize(dt)
                                parse_success += 1
                            except:
                                parse_failed += 1
                                continue
                        else:
                            parse_failed += 1
                            continue
                        
                        # 3일 필터 체크
                        if not self.is_within_3_days(published_at):
                            continue
                        
                        # 이미지 추출
                        image_url = None
                        if 'media_content' in entry:
                            image_url = entry.media_content[0].get('url', '')
                        
                        if not image_url:
                            image_url = self.extract_image_from_url(link)
                        
                        # 요약
                        summary = entry.get('summary', '')
                        if summary:
                            summary = BeautifulSoup(summary, 'html.parser').get_text(strip=True)[:200]
                        else:
                            summary = None
                        
                        articles.append({
                            'title': title,
                            'url': link,
                            'source': feed.feed.get('title', 'Tistory'),
                            'publishedAt': published_at.isoformat(),
                            'imageUrl': image_url or '',
                            'summary': summary or ''
                        })
                    
                    except Exception as e:
                        logger.debug(f"[티스토리 RSS] 항목 파싱 오류: {e}")
                        continue
                
                logger.info(f"[티스토리 RSS] {rss_url}: 날짜 파싱 성공: {parse_success}, 실패: {parse_failed}")
            
            except Exception as e:
                logger.error(f"[티스토리 RSS] 크롤링 오류 ({rss_url}): {e}")
                continue
        
        return articles
    
    def filter_by_date(self, articles: List[Dict]) -> List[Dict]:
        """3일 필터 적용"""
        filtered = []
        dropped_no_date = 0
        dropped_old = 0
        
        for article in articles:
            published_at_str = article.get('publishedAt', '')
            if not published_at_str:
                dropped_no_date += 1
                continue
            
            try:
                published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                if published_at.tzinfo is None:
                    published_at = KST.localize(published_at)
                else:
                    published_at = published_at.astimezone(KST)
                
                if not self.is_within_3_days(published_at):
                    dropped_old += 1
                    continue
                
                filtered.append(article)
            
            except Exception as e:
                logger.debug(f"[날짜 필터] 파싱 실패: {published_at_str}: {e}")
                dropped_no_date += 1
                continue
        
        logger.info(f"[3일 필터] 입력: {len(articles)}개, 날짜 없음 제외: {dropped_no_date}개, 과거 제외: {dropped_old}개, 최종: {len(filtered)}개")
        
        return filtered
    
    def remove_duplicates(self, articles: List[Dict]) -> List[Dict]:
        """중복 제거"""
        seen_urls: Set[str] = set()
        unique_articles = []
        
        for article in articles:
            normalized_url = self.normalize_url(article.get('url', ''))
            
            if normalized_url in seen_urls or not normalized_url:
                continue
            
            seen_urls.add(normalized_url)
            unique_articles.append(article)
        
        logger.info(f"[중복 제거] {len(articles)}개 → {len(unique_articles)}개")
        return unique_articles
    
    def enhance_images(self, articles: List[Dict], max_workers: int = 5) -> List[Dict]:
        """이미지 URL이 없는 항목에 대해 og:image 추출 (동시성 제한)"""
        articles_needing_image = [a for a in articles if not a.get('imageUrl')]
        
        if not articles_needing_image:
            return articles
        
        logger.info(f"[이미지 개선] {len(articles_needing_image)}개 항목에 대해 이미지 추출 시작")
        
        def fetch_image(article):
            url = article.get('url', '')
            if not url:
                return article
            
            image_url = self.extract_image_from_url(url)
            if image_url:
                article['imageUrl'] = image_url
                return article
            return article
        
        # 동시성 제한으로 이미지 추출
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_image, article): article for article in articles_needing_image}
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.debug(f"[이미지 추출] 오류: {e}")
        
        image_success = sum(1 for a in articles if a.get('imageUrl'))
        logger.info(f"[이미지 개선] 완료: {image_success}/{len(articles)}개 항목에 이미지 있음 ({image_success/len(articles)*100:.1f}%)")
        
        return articles
    
    def crawl_category(self, category_key: str) -> List[Dict]:
        """카테고리별 뉴스 수집 (3일 필터 강제)"""
        if category_key not in self.CATEGORIES:
            logger.error(f"알 수 없는 카테고리: {category_key}")
            return []
        
        category_info = self.CATEGORIES[category_key]
        category_name = category_info['name']
        google_query = category_info.get('google_query', category_name)
        naver_query = category_info.get('naver_query', category_name)
        keywords = category_info.get('keywords', [])
        
        logger.info(f"=" * 60)
        logger.info(f"[크롤링 시작] 카테고리: {category_name} ({category_key})")
        logger.info(f"[시간 필터] {self.cutoff_date.isoformat()} ~ {self.now_kst.isoformat()}")
        
        all_articles = []
        target_count = 10
        
        # 1. 구글 뉴스 RSS
        try:
            articles = self.crawl_google_news(google_query, max_results=15)
            all_articles.extend(articles)
            logger.info(f"[구글 뉴스] {len(articles)}개 수집")
        except Exception as e:
            logger.error(f"[구글 뉴스] 오류: {e}")
        
        # 2. 네이버 뉴스 API (확장 가능)
        if len(all_articles) < target_count:
            try:
                articles = self.crawl_naver_news(naver_query, max_results=15)
                all_articles.extend(articles)
                logger.info(f"[네이버 뉴스] {len(articles)}개 수집")
                
                # 부족하면 페이지네이션 확장
                if len(all_articles) < target_count:
                    articles = self.crawl_naver_news(naver_query, max_results=15, start=16)
                    all_articles.extend(articles)
                    logger.info(f"[네이버 뉴스 확장] {len(articles)}개 추가 수집")
            except Exception as e:
                logger.error(f"[네이버 뉴스] 오류: {e}")
        
        # 3. 네이버 블로그 API (확장 가능)
        if len(all_articles) < target_count:
            try:
                articles = self.crawl_naver_blog(naver_query, max_results=15)
                all_articles.extend(articles)
                logger.info(f"[네이버 블로그] {len(articles)}개 수집")
                
                # 부족하면 페이지네이션 확장
                if len(all_articles) < target_count:
                    articles = self.crawl_naver_blog(naver_query, max_results=15, start=16)
                    all_articles.extend(articles)
                    logger.info(f"[네이버 블로그 확장] {len(articles)}개 추가 수집")
            except Exception as e:
                logger.error(f"[네이버 블로그] 오류: {e}")
        
        # 4. 추가 키워드로 확장 (부족할 때만)
        if len(all_articles) < target_count and len(keywords) > 1:
            logger.info(f"[키워드 확장] 추가 키워드로 검색 시작")
            for keyword in keywords[1:3]:  # 상위 2개 키워드만
                try:
                    articles = self.crawl_google_news(keyword, max_results=10)
                    all_articles.extend(articles)
                    logger.info(f"[구글 뉴스 확장] 키워드 '{keyword}': {len(articles)}개 수집")
                    
                    if len(all_articles) >= target_count:
                        break
                except Exception as e:
                    logger.error(f"[키워드 확장] 오류: {e}")
        
        # 5. 티스토리 RSS (fallback)
        if len(all_articles) < 5:
            try:
                articles = self.crawl_tistory_rss(max_results=5)
                all_articles.extend(articles)
                logger.info(f"[티스토리 RSS] {len(articles)}개 수집")
            except Exception as e:
                logger.error(f"[티스토리 RSS] 오류: {e}")
        
        # 3일 필터 적용 (강제)
        filtered_articles = self.filter_by_date(all_articles)
        
        # 중복 제거
        unique_articles = self.remove_duplicates(filtered_articles)
        
        # 이미지 개선 (이미지가 없는 항목에 대해)
        enhanced_articles = self.enhance_images(unique_articles)
        
        # 날짜순 정렬 (최신순)
        try:
            enhanced_articles.sort(key=lambda x: x.get('publishedAt', ''), reverse=True)
        except:
            pass
        
        # 날짜 범위 검증 로그
        if enhanced_articles:
            dates = [datetime.fromisoformat(a.get('publishedAt', '').replace('Z', '+00:00')) for a in enhanced_articles if a.get('publishedAt')]
            if dates:
                min_date = min(dates)
                max_date = max(dates)
                logger.info(f"[날짜 범위 검증] 최신: {max_date.isoformat()}, 최구: {min_date.isoformat()}")
                logger.info(f"[날짜 범위 검증] 모든 날짜가 {self.cutoff_date.isoformat()} 이후: {all(d >= self.cutoff_date for d in dates)}")
        
        logger.info(f"[최종 결과] {category_name}: {len(enhanced_articles)}개 기사")
        logger.info(f"=" * 60)
        
        return enhanced_articles[:30]  # 최대 30개 반환
    
    def get_all_categories(self) -> Dict:
        """모든 카테고리 정보 반환"""
        return {key: info['name'] for key, info in self.CATEGORIES.items()}
