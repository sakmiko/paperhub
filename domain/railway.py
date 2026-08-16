"""铁路交通月报数据采集模块

每月收集铁路交通领域的论文前沿、行业动态、政策资讯。
数据来源：
  - 学术论文：Crossref 按铁路期刊过滤（34本）
  - 微信公众号：搜狗微信搜索实时获取
  - 行业新闻：国家铁路局、中国城市轨道交通协会等网站
"""

import re
import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
from core.utils import PaperResult, fetch, dedup_results, sort_results


# ===== 铁路交通核心期刊（英文 16本） =====
RAILWAY_JOURNALS_EN = [
    "International Journal of Rail Transportation",
    "Journal of Rail Transport Planning & Management",
    "Railway Engineering Science",
    "Journal of Modern Transportation",
    "Urban Rail Transit",
    "Transportation Research Record",
    "Transportation Research Part A",
    "Transportation Research Part C",
    "Transportation Research Part E",
    "Transportation Science",
    "European Transport Research Review",
    "Journal of Transportation Engineering",
    "Transportation Safety and Environment",
    "Proceedings of the Institution of Mechanical Engineers Part F: Journal of Rail and Rapid Transit",
    "Vehicle System Dynamics",
    "Journal of Traffic and Transportation Engineering",
]

# ===== 铁路交通核心期刊（中文 18本） =====
RAILWAY_JOURNALS_CN = [
    "铁道学报",
    "中国铁道科学",
    "铁道科学与工程学报",
    "交通运输工程学报",
    "铁道工程学报",
    "铁道运输与经济",
    "中国铁路",
    "铁道机车车辆",
    "城市轨道交通研究",
    "铁路计算机应用",
    "高速铁路技术",
    "现代城市轨道交通",
    "轨道交通",
    "铁路通信信号工程技术",
    "机车电传动",
    "铁道建筑",
    "铁道勘察",
    "铁道标准设计",
]

# ===== 微信公众号推荐（20个） =====
WECHAT_ACCOUNTS = [
    {"name": "国家铁路局", "id": "国家铁路局", "desc": "官方政策发布、铁路科技创新规划"},
    {"name": "中国铁道学会", "id": "中国铁道学会", "desc": "铁路学术交流、技术报告、标准研制"},
    {"name": "中国城市轨道交通协会", "id": "中国城市轨道交通协会", "desc": "智慧城轨、绿色低碳、AI应用"},
    {"name": "铁路12306", "id": "铁路12306", "desc": "运营动态、行业技术热点"},
    {"name": "轨道交通科技图片库", "id": "铁科院", "desc": "轨道交通科技图片、技术文献"},
    {"name": "智慧城市行业分析", "id": "智慧城市行业分析", "desc": "交通大数据、智慧交通前沿"},
    {"name": "铁道知识局", "id": "铁道知识局", "desc": "铁路科普、行业知识"},
    {"name": "铁路视点", "id": "铁路视点", "desc": "铁路行业观察与分析"},
    {"name": "轨道世界", "id": "轨道世界", "desc": "轨道交通行业资讯"},
    {"name": "城市轨道交通", "id": "城市轨道交通", "desc": "城轨行业动态"},
    {"name": "高速铁路技术", "id": "高速铁路技术", "desc": "高铁技术前沿"},
    {"name": "中国铁路", "id": "中国铁路", "desc": "中国铁路官方资讯"},
    {"name": "铁道工程学报", "id": "铁道工程学报", "desc": "铁路工程学术成果"},
    {"name": "中国铁道科学研究院", "id": "铁科院", "desc": "铁路科研动态"},
    {"name": "轨道交通装备与技术", "id": "轨道交通装备与技术", "desc": "装备技术前沿"},
    {"name": "国际铁路快讯", "id": "国际铁路快讯", "desc": "国际铁路动态"},
    {"name": "铁路建设", "id": "铁路建设", "desc": "铁路建设资讯"},
    {"name": "现代轨道交通", "id": "现代轨道交通", "desc": "轨道交通综合资讯"},
    {"name": "交通运输部", "id": "交通运输部", "desc": "交通运输政策"},
    {"name": "世界轨道交通", "id": "世界轨道交通", "desc": "全球轨道交通资讯"},
]

# ===== 行业网站（10个） =====
INDUSTRY_SITES = [
    {"name": "国家铁路局", "url": "https://www.nra.gov.cn", "desc": "政策法规、科技创新规划"},
    {"name": "中国城市轨道交通协会", "url": "https://www.camet.org.cn", "desc": "行业动态、技术示范"},
    {"name": "交通运输部", "url": "https://www.mot.gov.cn", "desc": "综合交通运输政策"},
    {"name": "中国铁道学会", "url": "https://www.crs.org.cn", "desc": "学术交流、科技奖励"},
    {"name": "中国国家铁路集团", "url": "https://www.china-railway.com.cn", "desc": "铁路运营动态"},
    {"name": "中国中车", "url": "https://www.crrcgc.cc", "desc": "轨道交通装备技术"},
    {"name": "中国铁道科学研究院", "url": "https://www.rails.cn", "desc": "铁路科研"},
    {"name": "International Railway Journal", "url": "https://www.railjournal.com", "desc": "国际铁路新闻"},
    {"name": "Railway Gazette", "url": "https://www.railwaygazette.com", "desc": "全球铁路行业新闻"},
    {"name": "Global Railway Review", "url": "https://www.globalrailwayreview.com", "desc": "铁路技术评论"},
]


def search_wechat_articles(keywords: list, max_per_keyword: int = 10) -> list:
    """通过搜狗微信搜索获取公众号文章"""
    import requests, time
    from urllib.parse import urljoin

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    try:
        session.get("https://weixin.sogou.com/", timeout=10)
    except Exception:
        return []

    all_articles = []
    for keyword in keywords:
        try:
            resp = session.get(
                "https://weixin.sogou.com/weixin",
                params={"type": 2, "query": keyword, "page": 1},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            html = resp.text
            # 提取文章块
            items = re.findall(r'<li id="sogou_vr_\d+_box_\d+"[^>]*>.*?</li>', html, re.DOTALL)
            for item in items[:max_per_keyword]:
                title_match = re.search(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', item, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
                if not title:
                    continue
                link_match = re.search(r'<a[^>]*href="([^"]*)"', item)
                link = link_match.group(1) if link_match else ""
                if link and not link.startswith("http"):
                    link = urljoin("https://weixin.sogou.com", link)
                abstract_match = re.search(r'<p[^>]*class="txt-info"[^>]*>(.*?)</p>', item, re.DOTALL)
                abstract = re.sub(r'<[^>]+>', '', abstract_match.group(1)).strip() if abstract_match else ""
                title = title.replace("&ldquo;", "「").replace("&rdquo;", "」").replace("&mdash;", "—").replace("&nbsp;", " ")
                abstract = abstract.replace("&ldquo;", "「").replace("&rdquo;", "」").replace("&mdash;", "—").replace("&nbsp;", " ")
                all_articles.append({
                    "title": title,
                    "url": link,
                    "abstract": abstract[:200],
                    "source": "搜狗微信搜索",
                })
            time.sleep(1.5)
        except Exception:
            continue
    return all_articles


def collect_industry_news() -> list:
    """收集行业新闻（从国家铁路局等网站获取）"""
    import requests
    news = []
    # 国家铁路局
    try:
        resp = requests.get("https://www.nra.gov.cn", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            # 检测编码
            resp.encoding = resp.apparent_encoding or 'utf-8'
            html = resp.text
            # 提取所有链接文本
            titles = re.findall(r'<a[^>]*>(.*?)</a>', html, re.DOTALL)
            seen = set()
            for t in titles:
                t = re.sub(r'<[^>]+>', '', t).strip()
                if len(t) > 15 and len(t) < 80 and t not in seen:
                    seen.add(t)
                    news.append({"source": "国家铁路局", "title": t})
                    if len(news) >= 5:
                        break
    except Exception:
        pass
    # 中国城市轨道交通协会
    try:
        resp = requests.get("https://www.camet.org.cn", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding or 'utf-8'
            html = resp.text
            titles = re.findall(r'<a[^>]*>(.*?)</a>', html, re.DOTALL)
            seen = set()
            for t in titles:
                t = re.sub(r'<[^>]+>', '', t).strip()
                if len(t) > 10 and len(t) < 80 and t not in seen and ("轨道" in t or "城轨" in t or "交通" in t or "铁路" in t):
                    seen.add(t)
                    news.append({"source": "城市轨道交通协会", "title": t})
                    if len(news) >= 5:
                        break
    except Exception:
        pass
    # 交通运输部
    try:
        resp = requests.get("https://www.mot.gov.cn", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            html = resp.text
            titles = re.findall(r'<a[^>]*>(.*?)</a>', html, re.DOTALL)
            seen = set()
            for t in titles:
                t = re.sub(r'<[^>]+>', '', t).strip()
                if len(t) > 15 and len(t) < 80 and t not in seen and ("铁路" in t or "轨道" in t or "交通" in t):
                    seen.add(t)
                    news.append({"source": "交通运输部", "title": t})
                    if len(news) >= 3:
                        break
    except Exception:
        pass
    return news


def collect_papers(query: str, limit: int = 5, journals: list = None) -> list:
    """通过 Crossref 搜索铁路期刊论文"""
    if journals is None:
        journals = RAILWAY_JOURNALS_EN + RAILWAY_JOURNALS_CN

    from domain.transport import search_transport
    results = []
    for jname in journals[:8]:
        try:
            r = search_transport(query, journal=jname, limit=limit)
            results.extend(r)
        except Exception:
            continue
    return results


def collect_latest_railway_papers(limit_per_journal: int = 3) -> dict:
    """收集铁路交通领域最新论文，按期刊分组"""
    from domain.transport import search_transport
    report = {}
    all_journals = RAILWAY_JOURNALS_EN + RAILWAY_JOURNALS_CN
    for jname in all_journals:
        try:
            results = search_transport("railway train", journal=jname, limit=limit_per_journal)
            if results:
                report[jname] = results
        except Exception:
            continue
    return report


def get_report_summary() -> dict:
    """生成月报摘要数据"""
    return {
        "journals_count": len(RAILWAY_JOURNALS_EN) + len(RAILWAY_JOURNALS_CN),
        "journals_en": RAILWAY_JOURNALS_EN,
        "journals_cn": RAILWAY_JOURNALS_CN,
        "wechat_accounts": WECHAT_ACCOUNTS,
        "industry_sites": INDUSTRY_SITES,
    }