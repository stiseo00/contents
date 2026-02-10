import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import re
import feedparser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SportsCrawler:
    """스포츠 뉴스 및 블로그를 크롤링하는 클래스"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.today = datetime.now().date()
    
    def is_today_article(self, date_str: str) -> bool:
        """기사가 오늘 날짜인지 확인"""
        try:
            if not date_str:
                return False
            
            # 다양한 날짜 형식 처리
            date_patterns = [
                r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})',  # 2024-01-01, 2024.01.01
                r'(\d{1,2})시간 전',  # N시간 전
                r'(\d{1,2})분 전',   # N분 전
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, date_str)
                if match:
                    if '시간 전' in date_str or '분 전' in date_str:
                        return True
                    else:
                        year, month, day = match.groups()
                        article_date = datetime(int(year), int(month), int(day)).date()
                        return article_date == self.today
            
            return False
        except Exception as e:
            logger.error(f"날짜 파싱 오류: {e}")
            return False
    
    def crawl_naver_sports(self) -> List[Dict]:
        """네이버 스포츠 뉴스 크롤링"""
        articles = []
        
        try:
            # 네이버 스포츠 주요 뉴스
            url = 'https://sports.news.naver.com/index'
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 뉴스 항목 찾기 - 다양한 선택자 시도
            news_items = soup.select('div.text a, .home_news a, .news_area a')[:30]
            
            seen_links = set()
            
            for item in news_items:
                try:
                    link = item.get('href', '')
                    if not link or link in seen_links:
                        continue
                    
                    # 스포츠 뉴스 링크만 필터링
                    if 'sports.news.naver.com' not in link and not link.startswith('/'):
                        continue
                    
                    if not link.startswith('http'):
                        link = 'https://sports.news.naver.com' + link
                    
                    seen_links.add(link)
                    
                    title = item.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue
                    
                    # 간단한 요약 생성
                    summary = f"{title[:100]}..."
                    
                    articles.append({
                        'title': title,
                        'link': link,
                        'image': 'https://via.placeholder.com/400x250/667eea/ffffff?text=Naver+Sports',
                        'summary': summary,
                        'content': '',
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'Naver Sports'
                    })
                
                except Exception as e:
                    logger.error(f"네이버 스포츠 항목 파싱 오류: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"네이버 스포츠 크롤링 오류: {e}")
        
        return articles
    
    def crawl_daum_sports(self) -> List[Dict]:
        """다음 스포츠 뉴스 크롤링"""
        articles = []
        
        try:
            url = 'https://sports.daum.net/'
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 뉴스 항목 찾기 - 다양한 선택자 시도
            news_items = soup.select('a.link_txt, .tit_g, strong.tit_thumb a')[:30]
            
            seen_links = set()
            
            for item in news_items:
                try:
                    link = item.get('href', '')
                    if not link or link in seen_links:
                        continue
                    
                    if not link.startswith('http'):
                        link = 'https://sports.daum.net' + link
                    
                    seen_links.add(link)
                    
                    title = item.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue
                    
                    # 간단한 요약 생성
                    summary = f"{title[:100]}..."
                    
                    articles.append({
                        'title': title,
                        'link': link,
                        'image': 'https://via.placeholder.com/400x250/764ba2/ffffff?text=Daum+Sports',
                        'summary': summary,
                        'content': '',
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'Daum Sports'
                    })
                
                except Exception as e:
                    logger.error(f"다음 스포츠 항목 파싱 오류: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"다음 스포츠 크롤링 오류: {e}")
        
        return articles
    
    def get_article_details(self, url: str) -> Dict:
        """기사 상세 정보 가져오기"""
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 본문 추출
            content = ''
            article_body = soup.select_one('article, .article_body, .article_content, #articleBodyContents')
            if article_body:
                # 스크립트와 스타일 제거
                for script in article_body(['script', 'style']):
                    script.decompose()
                content = article_body.get_text(strip=True)
            
            # 요약 생성 (처음 200자)
            summary = content[:200] + '...' if len(content) > 200 else content
            
            # 이미지 추출
            image = ''
            og_image = soup.select_one('meta[property="og:image"]')
            if og_image:
                image = og_image.get('content', '')
            
            # 날짜 추출
            date = ''
            date_meta = soup.select_one('meta[property="article:published_time"]')
            if date_meta:
                date = date_meta.get('content', '')[:10]
            
            return {
                'content': content,
                'summary': summary,
                'image': image,
                'date': date
            }
        
        except Exception as e:
            logger.error(f"기사 상세 정보 가져오기 오류: {e}")
            return {}
    
    def crawl_rss_feeds(self) -> List[Dict]:
        """RSS 피드에서 스포츠 뉴스 가져오기"""
        articles = []
        
        # 주요 스포츠 RSS 피드
        rss_feeds = [
            'https://sports.news.naver.com/kfootball/news/index?isphoto=N',
            'https://sports.news.naver.com/wfootball/news/index?isphoto=N',
            'https://sports.news.naver.com/baseball/news/index?isphoto=N',
        ]
        
        for feed_url in rss_feeds:
            try:
                response = requests.get(feed_url, headers=self.headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 뉴스 링크 찾기
                news_links = soup.select('a')[:15]
                
                for link_tag in news_links:
                    try:
                        link = link_tag.get('href', '')
                        if not link or 'sports.news.naver.com' not in link:
                            continue
                        
                        title = link_tag.get_text(strip=True)
                        if not title or len(title) < 10:
                            continue
                        
                        summary = f"{title[:100]}..."
                        
                        articles.append({
                            'title': title,
                            'link': link,
                            'image': 'https://via.placeholder.com/400x250/48bb78/ffffff?text=Sports+News',
                            'summary': summary,
                            'content': '',
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'source': 'Sports News'
                        })
                    
                    except Exception as e:
                        logger.error(f"RSS 항목 파싱 오류: {e}")
                        continue
            
            except Exception as e:
                logger.error(f"RSS 피드 크롤링 오류: {e}")
                continue
        
        return articles
    
    def get_sample_news(self) -> List[Dict]:
        """샘플 스포츠 뉴스 생성 (데모용)"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        sample_articles = [
            {
                'title': '손흥민, 토트넘 복귀전에서 결승골...팬들 환호',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/667eea/ffffff?text=Son+Goal',
                'summary': '손흥민이 부상에서 복귀한 첫 경기에서 결승골을 터뜨리며 팀의 승리를 이끌었다. 후반 35분 왼쪽에서 받은 공을 오른발로 정확히 마무리하며 골망을 흔들었다...',
                'date': today,
                'source': 'Naver Sports'
            },
            {
                'title': 'KBO 개막전, 역대급 관중 몰려...야구 열기 뜨겁다',
                'link': 'https://sports.daum.net',
                'image': 'https://via.placeholder.com/400x250/764ba2/ffffff?text=KBO+Opening',
                'summary': '2026 KBO 리그 개막전에 역대 최다 관중이 몰리며 야구 열기를 실감케 했다. 전국 5개 구장에서 동시에 열린 개막전에는 총 15만명이 넘는 관중이 찾았다...',
                'date': today,
                'source': 'Daum Sports'
            },
            {
                'title': '김연경, V리그 MVP 수상..."팬들께 감사"',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/48bb78/ffffff?text=Kim+MVP',
                'summary': '배구 여제 김연경이 V리그 정규시즌 MVP를 수상했다. 시즌 평균 득점 1위를 기록하며 팀의 플레이오프 진출에 크게 기여한 공로를 인정받았다...',
                'date': today,
                'source': 'Sports News'
            },
            {
                'title': '메시, 인터 마이애미와 재계약...MLS 잔류 확정',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/667eea/ffffff?text=Messi+Contract',
                'summary': '리오넬 메시가 인터 마이애미와 2년 재계약을 체결하며 MLS 잔류를 확정지었다. 메시는 지난 시즌 팀의 우승을 이끌며 리그 최고의 선수로 평가받았다...',
                'date': today,
                'source': 'Naver Sports'
            },
            {
                'title': '박세리 인비테이셔널, 역대 최대 규모로 개최',
                'link': 'https://sports.daum.net',
                'image': 'https://via.placeholder.com/400x250/764ba2/ffffff?text=Golf+Tournament',
                'summary': '박세리 인비테이셔널 골프 대회가 역대 최대 규모로 개최된다. 총 상금 30억원 규모로 세계 랭킹 상위권 선수들이 대거 참가할 예정이다...',
                'date': today,
                'source': 'Daum Sports'
            },
            {
                'title': '류현진, 시즌 첫 승...7이닝 무실점 호투',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/48bb78/ffffff?text=Ryu+Win',
                'summary': '류현진이 시즌 첫 승을 거두며 부활을 알렸다. 7이닝 동안 4개의 안타만 허용하며 무실점 호투를 펼쳤고, 팀은 5-0으로 승리했다...',
                'date': today,
                'source': 'Sports News'
            },
            {
                'title': 'NBA 플레이오프, 한국 시간 새벽 시작...관전 포인트는?',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/667eea/ffffff?text=NBA+Playoffs',
                'summary': 'NBA 플레이오프가 본격적으로 시작된다. 동부와 서부 각 8개 팀이 우승을 향한 치열한 경쟁을 펼칠 예정이며, 올해는 어느 때보다 전력이 균등해 예측이 어렵다...',
                'date': today,
                'source': 'Naver Sports'
            },
            {
                'title': '황희찬, 울버햄튼 올 시즌 최고의 선수 선정',
                'link': 'https://sports.daum.net',
                'image': 'https://via.placeholder.com/400x250/764ba2/ffffff?text=Hwang+Award',
                'summary': '황희찬이 울버햄튼의 올 시즌 최고의 선수로 선정됐다. 리그 15골 7도움을 기록하며 팀의 중위권 안착에 결정적인 역할을 했다는 평가를 받았다...',
                'date': today,
                'source': 'Daum Sports'
            },
            {
                'title': '한국 여자 배구, 올림픽 예선 1차전 승리',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/48bb78/ffffff?text=Volleyball+Win',
                'summary': '한국 여자 배구 대표팀이 올림픽 예선 1차전에서 승리를 거뒀다. 세트 스코어 3-1로 상대를 제압하며 본선 진출에 한 발 다가섰다...',
                'date': today,
                'source': 'Sports News'
            },
            {
                'title': '프리미어리그, 우승 경쟁 3파전 돌입',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/667eea/ffffff?text=Premier+League',
                'summary': '프리미어리그 우승 경쟁이 막판 3파전으로 접어들었다. 맨시티, 아스날, 리버풀이 승점 2점 차 이내에서 치열한 경쟁을 벌이고 있다...',
                'date': today,
                'source': 'Naver Sports'
            },
            {
                'title': '이강인, PSG에서 주전 경쟁력 입증',
                'link': 'https://sports.daum.net',
                'image': 'https://via.placeholder.com/400x250/764ba2/ffffff?text=Lee+PSG',
                'summary': '이강인이 PSG에서 주전 경쟁력을 확실히 입증했다. 최근 5경기 연속 선발 출장하며 2골 3도움을 기록, 팀 공격의 핵심으로 자리잡았다...',
                'date': today,
                'source': 'Daum Sports'
            },
            {
                'title': 'WBC 야구, 한국 대표팀 명단 발표',
                'link': 'https://sports.news.naver.com',
                'image': 'https://via.placeholder.com/400x250/48bb78/ffffff?text=WBC+Korea',
                'summary': 'WBC 야구 대회에 출전할 한국 대표팀 명단이 발표됐다. MLB와 KBO의 스타 선수들이 대거 포함되며 역대 최강 전력을 갖췄다는 평가다...',
                'date': today,
                'source': 'Sports News'
            }
        ]
        
        return sample_articles
    
    def get_all_sports_news(self) -> List[Dict]:
        """모든 소스에서 스포츠 뉴스 가져오기"""
        all_articles = []
        
        logger.info("스포츠 뉴스 크롤링 시작...")
        
        # 실제 크롤링 시도
        try:
            # 네이버 스포츠
            logger.info("네이버 스포츠 크롤링 중...")
            naver_articles = self.crawl_naver_sports()
            all_articles.extend(naver_articles)
            logger.info(f"네이버 스포츠: {len(naver_articles)}개 기사")
            
            # 다음 스포츠
            logger.info("다음 스포츠 크롤링 중...")
            daum_articles = self.crawl_daum_sports()
            all_articles.extend(daum_articles)
            logger.info(f"다음 스포츠: {len(daum_articles)}개 기사")
            
            # RSS 피드
            logger.info("RSS 피드 크롤링 중...")
            rss_articles = self.crawl_rss_feeds()
            all_articles.extend(rss_articles)
            logger.info(f"RSS 피드: {len(rss_articles)}개 기사")
        except Exception as e:
            logger.error(f"크롤링 오류: {e}")
        
        # 크롤링 결과가 없으면 샘플 데이터 사용
        if len(all_articles) < 5:
            logger.info("크롤링 결과가 부족하여 샘플 데이터를 사용합니다...")
            all_articles = self.get_sample_news()
        
        # 중복 제거 (타이틀 기준)
        seen_titles = set()
        unique_articles = []
        
        for article in all_articles:
            if article['title'] and article['title'] not in seen_titles:
                seen_titles.add(article['title'])
                unique_articles.append(article)
        
        logger.info(f"총 {len(unique_articles)}개의 고유 기사 수집 완료")
        
        return unique_articles[:50]  # 최대 50개 반환


if __name__ == "__main__":
    crawler = SportsCrawler()
    articles = crawler.get_all_sports_news()
    
    print(f"\n총 {len(articles)}개의 스포츠 뉴스를 찾았습니다.\n")
    
    for i, article in enumerate(articles[:5], 1):
        print(f"{i}. {article['title']}")
        print(f"   출처: {article['source']}")
        print(f"   링크: {article['link']}")
        print(f"   요약: {article['summary'][:100]}...")
        print()
