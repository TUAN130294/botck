# -*- coding: utf-8 -*-
# news_service.py — Dịch vụ tin tức nâng cao cho Bot Chứng khoán
# Áp dụng các cải tiến: Thêm nguồn scraping, cải thiện phân tích sentiment và loại tin.

import feedparser
import logging
import os
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from collections import namedtuple
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin

# THAY ĐỔI: Thêm thư viện VADER để phân tích cảm xúc
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

log = logging.getLogger(__name__)

# Create a session with retry capabilities (module-level for reuse)
session = requests.Session()
retry = Retry(connect=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

# Cấu trúc dữ liệu cho tin tức
NewsArticle = namedtuple("NewsArticle", ["source", "title", "link", "published", "sentiment", "type", "related_tickers", "sentiment_score"]) # THAY ĐỔI: Thêm sentiment_score

def _analyze_sentiment(text: str) -> Dict[str, Any]:
    """THAY ĐỔI: Phân tích cảm xúc mở rộng dựa trên từ khóa tiếng Việt và VADER."""
    positive_keywords = [
        "lãi", "lợi nhuận", "tăng trưởng", "phát triển", "mở rộng", "thành công", "chia cổ tức", 
        "thoái vốn", "được phép", "tích cực", "tăng", "tăng điểm", "mua ròng", "hồi phục", "bứt phá",
        "khai trương", "ra mắt", "hợp tác", "đầu tư", "dự án", "công trình", "sản phẩm mới", "thị trường",
        "xuất khẩu", "nhập khẩu", "hợp đồng", "đối tác", "công nghệ", "sáng tạo", "hiệu quả", "thành tựu",
        "tăng trưởng", "phục hồi", "ổn định", "cải thiện", "tích cực", "lạc quan", "thuận lợi", "cơ hội",
        "uptrend", "bullish", "breakout", "tích lũy", "hồi phục mạnh"
    ]
    negative_keywords = [
        "lỗ", "giảm", "suy giảm", "thua lỗ", "phạt", "đình chỉ", "đóng cửa", "bán tháo", 
        "căng thẳng", "tiêu cực", "giảm điểm", "bán ròng", "lao dốc", "sụt giảm", "khó khăn",
        "thách thức", "rủi ro", "thiệt hại", "tranh chấp", "kiện tụng", "vi phạm", "sự cố", "tai nạn",
        "ô nhiễm", "lãng phí", "thất bại", "đình trệ", "chậm trễ", "hủy bỏ", "thất thoát",
        "downtrend", "giảm sâu", "sụt giảm", "bán tháo", "hoảng loạn", "lo ngại", "bất ổn", "rủi ro",
        "mất điểm", "giảm sàn", "bán tháo", "thất vọng", "gây thất vọng", "điều chỉnh", "chỉnh kỹ thuật",
        "bearish", "pullback", "sụp đổ", "khủng hoảng"
    ]
    
    text_lower = text.lower()
    
    positive_count = sum(1 for k in positive_keywords if k in text_lower)
    negative_count = sum(1 for k in negative_keywords if k in text_lower)
    
    # THAY ĐỔI: Sử dụng VADER kết hợp với từ khóa để tăng độ chính xác
    analyzer = SentimentIntensityAnalyzer()
    vader_score = analyzer.polarity_scores(text_lower)['compound']

    sentiment = "Trung tính"
    if positive_count > negative_count + 1:
        sentiment = "Tích cực"
    elif negative_count > positive_count + 1:
        sentiment = "Tiêu cực"
    
    # Ưu tiên VADER nếu score mạnh
    if vader_score > 0.5:
        sentiment = "Tích cực"
    elif vader_score < -0.5:
        sentiment = "Tiêu cực"

    return {"sentiment": sentiment, "score": vader_score}

def _classify_news(text: str) -> str:
    """THAY ĐỔI: Phân loại tin tức mở rộng với nhiều keyword hơn."""
    text_lower = text.lower()
    
    macro_keywords = [
        "lãi suất", "fed", "chính sách", "gdp", "vn-index", "thị trường", "chứng khoán", "ngân hàng nhà nước",
        "chính phủ", "quốc hội", "luật", "nghị định", "thông tư", "tỷ giá", "lạm phát", "tăng trưởng kinh tế",
        "xuất khẩu", "nhập khẩu", "cán cân thương mại", "dự trữ ngoại hối", "ngân sách", "thuế", "cục thuế",
        "bộ tài chính", "ngân hàng trung ương", "tiền tệ", "tín dụng", "đầu tư công", "hạ tầng", "uptrend", 
        "downtrend", "tăng điểm", "giảm điểm", "chỉ số", "vốn hóa", "thanh khoản", "giao dịch", "khối ngoại",
        "bán ròng", "mua ròng", "thanh khoản", "phiên giao dịch", "sàn chứng khoán", "hose", "hnx", "upcom",
        "chỉ số chứng khoán", "thị trường toàn cầu", "fed rate"
    ]
    
    company_keywords = [
        "cổ tức", "kết quả kinh doanh", "lợi nhuận", "thoái vốn", "đhđcđ", "công ty", "doanh nghiệp",
        "ban lãnh đạo", "giám đốc", "chủ tịch", "cổ đông", "cổ phiếu", "niêm yết", "ipo", "phát hành",
        "hợp đồng", "dự án", "sản phẩm", "dịch vụ", "thương hiệu", "chi nhánh", "văn phòng", "khai trương",
        "hoạt động", "sản xuất", "kinh doanh", "thị trường", "ngành nghề", "lĩnh vực",
        "báo cáo tài chính", "doanh thu", "lợi nhuận ròng", "kế hoạch kinh doanh"
    ]
    
    sector_keywords = [
        "nhóm ngành", "ngân hàng", "bất động sản", "chứng khoán", "dầu khí", "thép", "xi măng",
        "dệt may", "thủy sản", "nông nghiệp", "du lịch", "vận tải", "viễn thông", "công nghệ",
        "y tế", "giáo dục", "tài chính", "bảo hiểm", "xây dựng", "năng lượng", "môi trường",
        "xe buýt", "giao thông", "hàng không", "điện", "nước", "viễn thông", "bán dẫn", "chip",
        "ngành ngân hàng", "bất động sản công nghiệp"
    ]
    
    macro_count = sum(1 for k in macro_keywords if k in text_lower)
    company_count = sum(1 for k in company_keywords if k in text_lower)
    sector_count = sum(1 for k in sector_keywords if k in text_lower)
    
    if macro_count > max(company_count, sector_count):
        return "Vĩ mô"
    elif company_count > max(macro_count, sector_count):
        return "Doanh nghiệp"
    elif sector_count > max(macro_count, company_count):
        return "Ngành"
    return "Khác"

def _find_related_tickers(text: str, all_tickers: List[str]) -> List[str]:
    """Tìm mã cổ phiếu liên quan trong tiêu đề."""
    found = []
    text_upper = text.upper()
    
    for ticker in all_tickers:
        if re.search(r'\b' + re.escape(ticker) + r'\b', text_upper):
            found.append(ticker)
    
    if not found:
        stock_keywords = ['CHỨNG KHOÁN', 'CỔ PHIẾU', 'VN-INDEX', 'VN30', 'HOSE', 'HNX', 'UPCOM', 'THỊ TRƯỜNG', 'GIAO DỊCH', 'VNINDEX']
        if any(keyword in text_upper for keyword in stock_keywords):
            common_tickers = ['VNINDEX', 'VN30', 'SSI', 'TCB', 'VCB', 'HPG', 'VNM', 'FPT', 'MWG', 'VIC']
            for ticker in common_tickers:
                if ticker in all_tickers:
                    found.append(ticker)
                    if len(found) >= 3:
                        break
    
    return list(set(found))

def fetch_and_analyze_news(sources: List[Dict[str, str]], all_watch_list: List[str], max_per_source: int = 15) -> List[NewsArticle]: # THAY ĐỔI: Tăng max_per_source
    """
    THAY ĐỔI: Lấy tin tức từ nhiều nguồn, phân tích cảm xúc và phân loại.
    Kết hợp cả RSS feed và scraping để lấy được nhiều tin tức nhất.
    """
    log.info("Bắt đầu lấy và phân tích tin tức (Cải tiến).")
    all_articles = []
    
    # Lấy tin từ RSS feeds
    for source in sources:
        try:
            response = session.get(source["url"], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml-xml') or BeautifulSoup(response.content, 'html.parser')
            entries = soup.find_all('item') or soup.find_all('entry')
            
            for entry in entries[:max_per_source]:
                title_tag = entry.find('title')
                link_tag = entry.find('link')
                pubdate_tag = entry.find('pubDate') or entry.find('updated') or entry.find('published')
                
                if title_tag and link_tag:
                    title = title_tag.text.strip()
                    link = link_tag.get('href', link_tag.text.strip())
                    published = pubdate_tag.text.strip() if pubdate_tag else 'N/A'
                    sentiment_data = _analyze_sentiment(title) # THAY ĐỔI: Lấy cả score
                    news_type = _classify_news(title)
                    related_tickers = _find_related_tickers(title, all_watch_list)
                    all_articles.append(NewsArticle(
                        source=source['name'], 
                        title=title, 
                        link=link, 
                        published=published, 
                        sentiment=sentiment_data['sentiment'], 
                        type=news_type, 
                        related_tickers=related_tickers,
                        sentiment_score=sentiment_data['score'] # THAY ĐỔI: Thêm score
                    ))
        except Exception as e:
            log.warning(f"Lỗi RSS {source['name']}: {e}")

    # THAY ĐỔI: Thêm scraping từ các nguồn như CafeF và Vietstock
    scraped_articles = _scrape_additional_news(all_watch_list, max_articles=max_per_source)
    all_articles.extend(scraped_articles)
    
    # Lọc trùng dựa trên title và link
    unique_articles = []
    seen = set()
    for art in all_articles:
        key = (art.title, art.link)
        if key not in seen:
            seen.add(key)
            # THAY ĐỔI: Không lọc quá chặt, giữ lại tin quan trọng kể cả không có ticker
            if art.related_tickers or art.type in ["Vĩ mô", "Ngành"] or art.sentiment_score != 0:
                unique_articles.append(art)
    
    # Sắp xếp theo thời gian (giả định scraping lấy tin mới nhất trước)
    # Hoặc sắp xếp theo độ quan trọng (sentiment score tuyệt đối)
    unique_articles.sort(key=lambda x: abs(x.sentiment_score), reverse=True)

    log.info(f"Tổng cộng đã lấy và phân tích {len(unique_articles)} tin tức (sau khi lọc).")
    return unique_articles

def format_news_for_ai(structured_news: Dict[str, Any]) -> str:
    """Định dạng dữ liệu tin tức có cấu trúc để chèn vào prompt của AI."""
    return ""

def fetch_structured_news_from_api(tickers: List[str]) -> Optional[Dict[str, Any]]:
    """CHỨC NĂNG TƯƠNG LAI: Lấy dữ liệu tin tức có cấu trúc từ NewsData.io."""
    return None

# Các hàm scraping giữ nguyên nhưng tăng max_articles trong _scrape_cafef_news và _scrape_vietstock_news lên 15.
def _scrape_additional_news(all_watch_list: List[str], max_articles: int = 15) -> List[NewsArticle]: # THAY ĐỔI: Tăng max_articles
    """Scraping tin tức từ CafeF và Vietstock."""
    scraped_articles = []
    
    try:
        # Scraping CafeF với số lượng lớn hơn
        cafef_articles = _scrape_cafef_news(all_watch_list, max_articles)
        scraped_articles.extend(cafef_articles)
        
        # Scraping Vietstock với số lượng lớn hơn
        vietstock_articles = _scrape_vietstock_news(all_watch_list, max_articles)
        scraped_articles.extend(vietstock_articles)
        
        log.info(f"Đã scraping được tổng cộng {len(scraped_articles)} tin từ cả hai nguồn")
        
    except Exception as e:
        log.error(f"Lỗi khi scraping tin tức: {e}")
    
    return scraped_articles

def _scrape_cafef_news(all_watch_list: List[str], max_articles: int = 15) -> List[NewsArticle]: # THAY ĐỔI: Tăng max_articles
    """Scraping tin tức từ CafeF."""
    articles = []
    try:
        urls_to_scrape = [
            'https://cafef.vn/',
            'https://cafef.vn/thi-truong-chung-khoan.chn',
            'https://cafef.vn/doanh-nghiep.chn',
            'https://cafef.vn/tai-chinh-ngan-hang.chn'
        ]
        
        for base_url in urls_to_scrape:
            if len(articles) >= max_articles:
                break
                
            try:
                response = session.get(base_url, timeout=15)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    all_links = soup.find_all('a', href=True)
                    
                    for link_tag in all_links:
                        if len(articles) >= max_articles:
                            break
                            
                        try:
                            href = link_tag.get('href', '')
                            title = link_tag.get_text(strip=True)
                            
                            if not href or href.startswith('#') or href.startswith('javascript:'):
                                continue
                                
                            if any(keyword in href.lower() for keyword in ['/tin-tuc/', '/kinh-te/', '/tai-chinh/', '/bat-dong-san/', '/doanh-nghiep/', '/thi-truong-chung-khoan', '/chung-khoan/', '/dau-tu/', '/thi-truong/', '/ngan-hang/', '/bat-dong-san/', '/dau-tu/', '/kinh-doanh/']):
                                if any(skip in href.lower() for skip in ['/tag/', '/author/', '/search/', '.chn', '/rss/']):
                                    continue
                                    
                                if len(title) > 8 and len(title) < 300 and title.strip() and href.startswith('/'):
                                    link_url = urljoin('https://cafef.vn/', href)
                                    sentiment_data = _analyze_sentiment(title) # THAY ĐỔI: Lấy cả score
                                    news_type = _classify_news(title)
                                    related_tickers = _find_related_tickers(title, all_watch_list)
                                    
                                    if not any(art.title == title for art in articles):
                                        articles.append(NewsArticle(
                                            source='CafeF',
                                            title=title,
                                            link=link_url,
                                            published='N/A',
                                            sentiment=sentiment_data['sentiment'],
                                            type=news_type,
                                            related_tickers=related_tickers,
                                            sentiment_score=sentiment_data['score'] # THAY ĐỔI: Thêm score
                                        ))
                        
                        except Exception as e:
                            continue
                            
            except Exception as e:
                log.warning(f"Không thể scraping trang {base_url}: {e}")
                continue
                    
        log.info(f"Đã scraping được {len(articles)} tin từ CafeF")
                        
    except Exception as e:
        log.error(f"Lỗi khi scraping CafeF: {e}")
        
    return articles

def _scrape_vietstock_news(all_watch_list: List[str], max_articles: int = 15) -> List[NewsArticle]: # THAY ĐỔI: Tăng max_articles
    """Scraping tin tức từ Vietstock."""
    articles = []
    try:
        urls_to_scrape = [
            'https://vietstock.vn/',
            'https://vietstock.vn/chung-khoan.htm',
            'https://vietstock.vn/tai-chinh-ngan-hang.htm',
            'https://vietstock.vn/kinh-te.htm'
        ]
        
        for base_url in urls_to_scrape:
            if len(articles) >= max_articles:
                break
                
            try:
                response = session.get(base_url, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    all_links = soup.find_all('a', href=True)
                    
                    for link_tag in all_links:
                        if len(articles) >= max_articles:
                            break
                            
                        try:
                            href = link_tag.get('href', '')
                            title = link_tag.get_text(strip=True)
                            
                            if not href or href.startswith('#') or href.startswith('javascript:'):
                                continue
                                
                            if any(keyword in href.lower() for keyword in ['/tin-tuc/', '/kinh-te/', '/tai-chinh/', '/bat-dong-san/', '/doanh-nghiep/', '/nhan-dinh/', '/phan-tich', '/chung-khoan/', '/ngan-hang/', '/dau-tu/']):
                                if len(title) > 8 and len(title) < 250 and title.strip():
                                    link_url = urljoin('https://vietstock.vn/', href)
                                    sentiment_data = _analyze_sentiment(title) # THAY ĐỔI: Lấy cả score
                                    news_type = _classify_news(title)
                                    related_tickers = _find_related_tickers(title, all_watch_list)
                                    
                                    if not any(art.title == title for art in articles):
                                        articles.append(NewsArticle(
                                            source='Vietstock',
                                            title=title,
                                            link=link_url,
                                            published='N/A',
                                            sentiment=sentiment_data['sentiment'],
                                            type=news_type,
                                            related_tickers=related_tickers,
                                            sentiment_score=sentiment_data['score'] # THAY ĐỔI: Thêm score
                                        ))
                        
                        except Exception as e:
                            continue
                            
            except Exception as e:
                log.warning(f"Không thể scraping trang {base_url}: {e}")
                continue
                    
        log.info(f"Đã scraping được {len(articles)} tin từ Vietstock")
        
    except Exception as e:
        log.error(f"Lỗi khi scraping Vietstock: {e}")
        
    return articles