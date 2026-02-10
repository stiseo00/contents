import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import re
import feedparser
import logging
from urllib.parse import urlparse, urljoin, urlunparse, quote
import time
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CategoryCrawler:
    """카테고리별 뉴스 및 블로그를 크롤링하는 클래스 (개선 버전)"""
    
    # 카테고리 정의
    CATEGORIES = {
        'health': {
            'name': '건강·운동',
            'keywords': ['다이어트', '운동', '자세교정', '통증', '헬스', '요가', '필라테스', '근력운동'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'food': {
            'name': '맛집·레시피',
            'keywords': ['맛집', '레시피', '요리', '혼밥', '간단요리', '다이어트식', '카페', '식당'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'finance': {
            'name': '재테크·돈관리',
            'keywords': ['재테크', '투자', '주식', '가계부', '절약', '소비', '금융', '저축'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'travel': {
            'name': '여행·주말나들이',
            'keywords': ['여행', '주말', '당일치기', '여행지', '명소', '관광', '데이트코스'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'relationship': {
            'name': '연애·관계·심리',
            'keywords': ['연애', '심리', '관계', 'MBTI', '대화법', '갈등', '커플', '데이트'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'self_improvement': {
            'name': '자기계발·공부법',
            'keywords': ['자기계발', '공부법', '시간관리', '독서', '자격증', '학습', '집중력'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'it': {
            'name': 'IT·앱·AI 트렌드',
            'keywords': ['앱', 'AI', 'IT', '기술', '스마트폰', '생산성', '디지털', '소프트웨어'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'beauty': {
            'name': '뷰티·패션·그루밍',
            'keywords': ['뷰티', '패션', '스킨케어', '화장품', '스타일링', '옷', '코디', '그루밍'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'home': {
            'name': '집·인테리어·살림',
            'keywords': ['인테리어', '집꾸미기', '정리정돈', '청소', '가구', '리모델링', '살림'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'hobby': {
            'name': '취미·문화생활',
            'keywords': ['영화', '드라마', '전시', '음악', '취미', '문화', '공연', '독서'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'family': {
            'name': '육아·가족·반려동물',
            'keywords': ['육아', '아이', '반려동물', '강아지', '고양이', '가족', '육아팁'],
            'sources': ['naver_blog', 'daum_blog', 'tistory']
        },
        'sports': {
            'name': '스포츠',
            'keywords': ['스포츠', '축구', '야구', '농구', '배구', '운동', '경기'],
            'sources': ['naver_sports', 'daum_sports']
        }
    }
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.today = datetime.now().date()
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def normalize_url(self, url: str) -> str:
        """URL 정규화 (중복 제거용)"""
        try:
            parsed = urlparse(url)
            # 쿼리 파라미터 제거 (일부는 유지)
            keep_params = ['id', 'postId']
            if parsed.query:
                params = {}
                for param in parsed.query.split('&'):
                    if '=' in param:
                        key, val = param.split('=', 1)
                        if key in keep_params:
                            params[key] = val
                query = '&'.join(f'{k}={v}' for k, v in params.items()) if params else ''
            else:
                query = ''
            
            # 프래그먼트 제거
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path.rstrip('/'),
                parsed.params,
                query,
                ''  # fragment 제거
            ))
            return normalized
        except Exception:
            return url
    
    def title_similarity(self, title1: str, title2: str) -> float:
        """제목 유사도 계산"""
        return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
    
    def extract_image(self, soup: BeautifulSoup, url: str) -> str:
        """이미지 추출 (og:image → twitter:image → 본문 이미지 순서)"""
        # 1. og:image
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image and og_image.get('content'):
            img_url = og_image.get('content')
            if img_url.startswith('http'):
                return img_url
            elif img_url.startswith('//'):
                return 'https:' + img_url
            elif img_url.startswith('/'):
                parsed = urlparse(url)
                return f"{parsed.scheme}://{parsed.netloc}{img_url}"
        
        # 2. twitter:image
        twitter_image = soup.select_one('meta[name="twitter:image"]')
        if twitter_image and twitter_image.get('content'):
            img_url = twitter_image.get('content')
            if img_url.startswith('http'):
                return img_url
        
        # 3. 본문의 첫 번째 이미지
        article_img = soup.select_one('article img, .post img, .content img, .entry-content img')
        if article_img and article_img.get('src'):
            img_url = article_img.get('src')
            if img_url.startswith('http'):
                return img_url
            elif img_url.startswith('//'):
                return 'https:' + img_url
            elif img_url.startswith('/'):
                parsed = urlparse(url)
                return f"{parsed.scheme}://{parsed.netloc}{img_url}"
        
        return ''
    
    def extract_summary(self, soup: BeautifulSoup, content: str = '') -> str:
        """요약 추출 (meta description → 본문 첫 2-3문장)"""
        # 1. meta description
        meta_desc = soup.select_one('meta[name="description"], meta[property="og:description"]')
        if meta_desc and meta_desc.get('content'):
            desc = meta_desc.get('content').strip()
            if len(desc) >= 80:
                return self.clean_text(desc[:160])
        
        # 2. 본문에서 추출
        if content:
            # 불필요한 태그 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
                tag.decompose()
            
            # 본문 찾기
            article_body = soup.select_one('article, .post-content, .entry-content, .article-body, .content')
            if article_body:
                text = article_body.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            # 첫 2-3문장 추출
            sentences = re.split(r'[.!?]\s+', text)
            summary = ''
            for sent in sentences[:3]:
                if len(summary) + len(sent) < 160:
                    summary += sent + '. '
                else:
                    break
            
            summary = summary.strip()
            if len(summary) >= 80:
                return self.clean_text(summary[:160])
        
        return ''
    
    def clean_text(self, text: str) -> str:
        """텍스트 정리 (줄바꿈, 특수문자 정리)"""
        # 연속 공백 제거
        text = re.sub(r'\s+', ' ', text)
        # 줄바꿈 제거
        text = text.replace('\n', ' ').replace('\r', ' ')
        # HTML 엔티티 디코딩
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return text.strip()
    
    def parse_date(self, soup: BeautifulSoup, url: str) -> Optional[datetime]:
        """날짜 파싱 (다양한 소스 시도)"""
        # 1. og:published_time
        og_date = soup.select_one('meta[property="article:published_time"]')
        if og_date and og_date.get('content'):
            try:
                return datetime.fromisoformat(og_date.get('content').replace('Z', '+00:00'))
            except:
                pass
        
        # 2. time 태그
        time_tag = soup.select_one('time[datetime]')
        if time_tag:
            try:
                return datetime.fromisoformat(time_tag.get('datetime').replace('Z', '+00:00'))
            except:
                pass
        
        # 3. 날짜 패턴 찾기
        date_patterns = [
            r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})',
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일'
        ]
        
        text = soup.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    year, month, day = match.groups()
                    return datetime(int(year), int(month), int(day))
                except:
                    pass
        
        return None
    
    def fetch_with_retry(self, url: str, params: Optional[Dict] = None, max_retries: int = 3, timeout: int = 8) -> Optional[requests.Response]:
        """재시도 로직이 포함된 요청"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Too Many Requests
                    wait_time = (2 ** attempt) + (time.time() % 1)  # 백오프
                    logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries}) for {url}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
        
        return None
    
    def crawl_article_details(self, url: str) -> Optional[Dict]:
        """기사 상세 정보 크롤링"""
        try:
            response = self.fetch_with_retry(url)
            if not response:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 제목 추출
            title = ''
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get('content'):
                title = og_title.get('content').strip()
            else:
                title_tag = soup.select_one('title, h1, .title')
                if title_tag:
                    title = title_tag.get_text(strip=True)
            
            if not title or len(title) < 5:
                return None
            
            # 이미지 추출
            image_url = self.extract_image(soup, url)
            
            # 요약 추출
            summary = self.extract_summary(soup, response.text)
            if not summary or len(summary) < 50:
                summary = title[:100] + '...'
            
            # 날짜 추출
            published_at = self.parse_date(soup, url)
            if not published_at:
                published_at = datetime.now()
            
            # 출처 추출
            domain = urlparse(url).netloc
            source = domain.replace('www.', '').split('.')[0].capitalize()
            
            return {
                'title': title,
                'url': url,
                'imageUrl': image_url,
                'summary': summary,
                'publishedAt': published_at.isoformat(),
                'source': source
            }
        
        except Exception as e:
            logger.error(f"기사 상세 크롤링 오류 ({url}): {e}")
            return None
    
    def crawl_naver_blog(self, keyword: str, max_results: int = 15) -> List[Dict]:
        """네이버 블로그 크롤링 (개선 - 실제 작동 버전)"""
        articles = []
        
        try:
            logger.info(f"[네이버 블로그] 키워드: {keyword}, 최대 {max_results}개")
            
            # 방법 1: RSS 피드 시도
            try:
                rss_url = f'https://search.naver.com/search.naver?where=post&query={quote(keyword)}&display={min(max_results, 50)}'
                feed = feedparser.parse(rss_url)
                if feed.entries:
                    logger.info(f"[네이버 블로그 RSS] 발견된 항목: {len(feed.entries)}개")
                    for entry in feed.entries[:max_results]:
                        try:
                            title = entry.get('title', '').strip()
                            link = entry.get('link', '')
                            summary = entry.get('summary', '')[:150] + '...' if entry.get('summary') else title[:100] + '...'
                            
                            # 이미지 찾기
                            image_url = ''
                            if 'media_content' in entry:
                                image_url = entry.media_content[0].get('url', '')
                            elif 'media_thumbnail' in entry:
                                image_url = entry.media_thumbnail[0].get('url', '')
                            
                            if title and link:
                                articles.append({
                                    'title': title,
                                    'url': link,
                                    'imageUrl': image_url,
                                    'summary': summary,
                                    'publishedAt': entry.get('published', datetime.now().isoformat()),
                                    'source': 'Naver Blog'
                                })
                        except Exception as e:
                            logger.debug(f"[네이버 블로그 RSS] 항목 파싱 오류: {e}")
                            continue
            except Exception as e:
                logger.debug(f"[네이버 블로그 RSS] 실패, HTML 파싱으로 전환: {e}")
            
            # 방법 2: HTML 파싱 (RSS 실패 시 또는 추가 수집)
            if len(articles) < max_results:
                url = 'https://search.naver.com/search.naver'
                params = {
                    'where': 'post',
                    'query': keyword,
                    'display': min(max_results * 2, 50)
                }
                
                response = self.fetch_with_retry(url, params=params, timeout=10)
                if response:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 실제 블로그 포스트 링크 찾기 (더 정확한 셀렉터)
                    blog_links = soup.select('a[href*="blog.naver.com/post"], a[href*="blog.me/post"]')
                    logger.info(f"[네이버 블로그 HTML] 발견된 링크: {len(blog_links)}개")
                    
                    seen_urls = set()
                    for link_tag in blog_links[:max_results * 2]:
                        try:
                            link = link_tag.get('href', '')
                            if not link or link in seen_urls:
                                continue
                            
                            # 상대 경로 처리
                            if link.startswith('/'):
                                continue
                            
                            # 실제 블로그 URL 추출
                            if 'url=' in link:
                                import urllib.parse
                                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                                if 'url' in parsed:
                                    link = parsed['url'][0]
                            
                            if not link.startswith('http'):
                                continue
                            
                            seen_urls.add(link)
                            
                            # 제목 찾기
                            title = link_tag.get_text(strip=True)
                            if not title or len(title) < 5:
                                # 부모 요소에서 제목 찾기
                                parent = link_tag.find_parent(['div', 'li', 'article'])
                                if parent:
                                    title_elem = parent.select_one('.title, h2, h3, .tit')
                                    if title_elem:
                                        title = title_elem.get_text(strip=True)
                            
                            if not title or len(title) < 5:
                                title = f"{keyword} 관련 글"
                            
                            # 요약 찾기
                            summary = ''
                            parent = link_tag.find_parent(['div', 'li', 'article'])
                            if parent:
                                summary_elem = parent.select_one('.sh_blog_passage, .api_txt_lines, .dsc_txt, p')
                                if summary_elem:
                                    summary = summary_elem.get_text(strip=True)
                            
                            if not summary or len(summary) < 50:
                                summary = title[:100] + '...'
                            else:
                                summary = summary[:150] + '...'
                            
                            articles.append({
                                'title': title,
                                'url': link,
                                'imageUrl': '',
                                'summary': summary,
                                'publishedAt': datetime.now().isoformat(),
                                'source': 'Naver Blog'
                            })
                            
                            if len(articles) >= max_results:
                                break
                            
                            time.sleep(0.1)
                        
                        except Exception as e:
                            logger.debug(f"[네이버 블로그 HTML] 항목 파싱 오류: {e}")
                            continue
            
            logger.info(f"[네이버 블로그] 최종 수집: {len(articles)}개")
        
        except Exception as e:
            logger.error(f"[네이버 블로그] 크롤링 오류: {e}", exc_info=True)
        
        return articles
    
    def crawl_daum_blog(self, keyword: str, max_results: int = 15) -> List[Dict]:
        """다음 블로그 크롤링 (개선)"""
        articles = []
        
        try:
            logger.info(f"[다음 블로그] 키워드: {keyword}, 최대 {max_results}개")
            url = 'https://search.daum.net/search'
            params = {
                'w': 'blog',
                'q': keyword,
                'DA': 'PGD'
            }
            
            logger.info(f"[다음 블로그] 요청 URL: {url}?w=blog&q={keyword}")
            response = self.fetch_with_retry(url, params=params, timeout=10)
            if not response:
                logger.warning(f"[다음 블로그] 요청 실패: {keyword}")
                return articles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 다양한 셀렉터 시도
            blog_items = soup.select('.wrap_cont a.f_link_b, .f_link_b, a[href*="blog.daum.net"]')
            logger.info(f"[다음 블로그] 발견된 항목 수: {len(blog_items)}")
            
            for item in blog_items[:max_results]:
                try:
                    title = item.get_text(strip=True)
                    link = item.get('href', '')
                    
                    if not title or len(title) < 5:
                        continue
                    
                    if not link.startswith('http'):
                        link = 'https://search.daum.net' + link
                    
                    # 기본 정보 수집
                    articles.append({
                        'title': title,
                        'url': link,
                        'imageUrl': '',
                        'summary': title[:100] + '...',
                        'publishedAt': datetime.now().isoformat(),
                        'source': 'Daum Blog'
                    })
                    
                    logger.debug(f"[다음 블로그] 수집: {title[:30]}...")
                    
                    time.sleep(0.2)
                
                except Exception as e:
                    logger.error(f"[다음 블로그] 항목 파싱 오류: {e}")
                    continue
            
            logger.info(f"[다음 블로그] 최종 수집: {len(articles)}개")
        
        except Exception as e:
            logger.error(f"[다음 블로그] 크롤링 오류: {e}", exc_info=True)
        
        return articles
    
    def crawl_tistory(self, keyword: str, max_results: int = 15) -> List[Dict]:
        """티스토리 블로그 크롤링 (개선)"""
        articles = []
        
        try:
            logger.info(f"[티스토리] 키워드: {keyword}, 최대 {max_results}개")
            url = 'https://search.naver.com/search.naver'
            params = {
                'where': 'post',
                'query': f'{keyword} site:tistory.com',
                'display': min(max_results, 50)
            }
            
            logger.info(f"[티스토리] 요청 URL: {url}?where=post&query={keyword} site:tistory.com")
            response = self.fetch_with_retry(url, params=params, timeout=10)
            if not response:
                logger.warning(f"[티스토리] 요청 실패: {keyword}")
                return articles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            blog_items = soup.select('.sh_blog_top, .api_subject_bx, a[href*="tistory.com"]')
            logger.info(f"[티스토리] 발견된 항목 수: {len(blog_items)}")
            
            for item in blog_items[:max_results]:
                try:
                    link_tag = item if item.name == 'a' else item.select_one('a')
                    if not link_tag:
                        continue
                    
                    title = link_tag.get_text(strip=True)
                    link = link_tag.get('href', '')
                    
                    if not title or len(title) < 5:
                        continue
                    
                    # 링크 정규화
                    if 'url=' in link:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        if 'url' in parsed:
                            link = parsed['url'][0]
                    
                    articles.append({
                        'title': title,
                        'url': link,
                        'imageUrl': '',
                        'summary': title[:100] + '...',
                        'publishedAt': datetime.now().isoformat(),
                        'source': 'Tistory'
                    })
                    
                    logger.debug(f"[티스토리] 수집: {title[:30]}...")
                    
                    time.sleep(0.2)
                
                except Exception as e:
                    logger.error(f"[티스토리] 항목 파싱 오류: {e}")
                    continue
            
            logger.info(f"[티스토리] 최종 수집: {len(articles)}개")
        
        except Exception as e:
            logger.error(f"[티스토리] 크롤링 오류: {e}", exc_info=True)
        
        return articles
    
    def remove_duplicates(self, articles: List[Dict]) -> List[Dict]:
        """중복 제거 (URL 정규화 + 제목 유사도)"""
        seen_urls: Set[str] = set()
        seen_titles: Set[str] = set()
        unique_articles = []
        
        for article in articles:
            # URL 정규화
            normalized_url = self.normalize_url(article.get('url', ''))
            
            # URL 중복 체크
            if normalized_url in seen_urls:
                continue
            
            # 제목 유사도 체크
            title = article.get('title', '').lower().strip()
            is_duplicate = False
            for seen_title in seen_titles:
                if self.title_similarity(title, seen_title) > 0.85:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_urls.add(normalized_url)
                seen_titles.add(title)
                unique_articles.append(article)
        
        logger.info(f"[중복 제거] {len(articles)}개 → {len(unique_articles)}개")
        return unique_articles
    
    def get_sample_articles(self, category_key: str, category_info: Dict, count: int = 10) -> List[Dict]:
        """샘플 기사 생성 (fallback용)"""
        category_name = category_info['name']
        keywords = category_info['keywords']
        today = datetime.now()
        
        samples = []
        for i in range(count):
            keyword = keywords[i % len(keywords)]
            samples.append({
                'title': f'{keyword} 관련 최신 정보 및 팁',
                'url': f'https://example.com/{category_key}/{i+1}',
                'imageUrl': '',
                'summary': f'{keyword}에 대한 유용한 정보와 실용적인 팁을 공유합니다. 전문가의 조언과 실제 경험을 바탕으로 한 내용을 확인해보세요.',
                'publishedAt': (today - timedelta(days=i)).isoformat(),
                'source': category_name
            })
        
        return samples
    
    def crawl_category(self, category_key: str) -> List[Dict]:
        """특정 카테고리의 뉴스/블로그 크롤링 (개선)"""
        if category_key not in self.CATEGORIES:
            logger.error(f"알 수 없는 카테고리: {category_key}")
            return []
        
        category_info = self.CATEGORIES[category_key]
        category_name = category_info['name']
        keywords = category_info['keywords']
        sources = category_info['sources']
        
        logger.info(f"=" * 60)
        logger.info(f"[크롤링 시작] 카테고리: {category_name} ({category_key})")
        logger.info(f"[키워드] {keywords[:4]}")
        logger.info(f"[소스] {sources}")
        
        all_articles = []
        
        # 각 키워드로 크롤링 (상위 4개 키워드 사용)
        for keyword in keywords[:4]:
            logger.info(f"[키워드 처리] {keyword}")
            try:
                if 'naver_blog' in sources:
                    articles = self.crawl_naver_blog(keyword, max_results=8)
                    all_articles.extend(articles)
                    logger.info(f"[네이버 블로그] {keyword}: {len(articles)}개 수집")
                    time.sleep(0.5)  # 도메인별 속도 제한
                
                if 'daum_blog' in sources:
                    articles = self.crawl_daum_blog(keyword, max_results=8)
                    all_articles.extend(articles)
                    logger.info(f"[다음 블로그] {keyword}: {len(articles)}개 수집")
                    time.sleep(0.5)
                
                if 'tistory' in sources:
                    articles = self.crawl_tistory(keyword, max_results=8)
                    all_articles.extend(articles)
                    logger.info(f"[티스토리] {keyword}: {len(articles)}개 수집")
                    time.sleep(0.5)
            
            except Exception as e:
                logger.error(f"[키워드 오류] {keyword}: {e}", exc_info=True)
                continue
        
        logger.info(f"[수집 완료] 총 {len(all_articles)}개")
        
        # 중복 제거
        unique_articles = self.remove_duplicates(all_articles)
        
        # 최소 10개 보장 (부족하면 샘플 추가)
        if len(unique_articles) < 10:
            logger.warning(f"[경고] {category_name} 크롤링 결과가 부족합니다 ({len(unique_articles)}개)")
            logger.info(f"[샘플 추가] {10 - len(unique_articles)}개 샘플 기사 추가")
            sample_count = 10 - len(unique_articles)
            samples = self.get_sample_articles(category_key, category_info, sample_count)
            unique_articles.extend(samples)
        
        # 날짜순 정렬 (최신순)
        try:
            unique_articles.sort(key=lambda x: x.get('publishedAt', ''), reverse=True)
        except:
            pass
        
        logger.info(f"[최종 결과] {category_name}: {len(unique_articles)}개 기사")
        logger.info(f"=" * 60)
        
        return unique_articles[:30]  # 최대 30개 반환
    
    def get_all_categories(self) -> Dict:
        """모든 카테고리 정보 반환"""
        return {key: info['name'] for key, info in self.CATEGORIES.items()}
