"""铁路交通月报数据采集模块

每月收集铁路交通领域的论文前沿、行业动态、政策资讯。
数据来源：
  - 学术论文：Crossref 按铁路期刊过滤
  - 行业新闻：国家铁路局、中国城市轨道交通协会等网站
  - 微信公众号：推荐关注列表（需手动阅读）
"""

import re
import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
from core.utils import PaperResult, fetch, dedup_results, sort_results


# ===== 铁路交通核心期刊（英文） =====
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

# ===== 铁路交通核心期刊（中文） =====
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

# ===== 微信公众号推荐 =====
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

# ===== 行业网站 =====
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


def collect_papers(query: str, limit: int = 5, journals: list = None) -> list:
    """通过 Crossref 搜索铁路期刊论文"""
    if journals is None:
        journals = RAILWAY_JOURNALS_EN + RAILWAY_JOURNALS_CN

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from domain.transport import search_transport

    results = []
    for jname in journals[:5]:  # 最多查5本期刊
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
            results = search_transport("", journal=jname, limit=limit_per_journal)
            if results:
                report[jname] = results
        except Exception:
            continue

    return report


def collect_industry_news() -> list:
    """收集行业新闻（从公开网站获取）"""
    news = []
    import requests
    from bs4 import BeautifulSoup

    # 国家铁路局最新动态
    try:
        resp = requests.get("https://www.nra.gov.cn", timeout=10)
        if resp.status_code == 200:
            # 提取新闻标题
            titles = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([^<]{10,80})</a>', resp.text)
            for t in titles[:5]:
                t = t.strip()
                if t and len(t) > 10:
                    news.append({"source": "国家铁路局", "title": t, "url": "https://www.nra.gov.cn"})
    except Exception:
        pass

    # 中国城市轨道交通协会
    try:
        resp = requests.get("https://www.camet.org.cn", timeout=10)
        if resp.status_code == 200:
            titles = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([^<]{10,80})</a>', resp.text)
            for t in titles[:5]:
                t = t.strip()
                if t and len(t) > 10 and "城轨" in t or "轨道" in t or "交通" in t:
                    news.append({"source": "中国城市轨道交通协会", "title": t, "url": "https://www.camet.org.cn"})
    except Exception:
        pass

    return news


def get_report_summary() -> dict:
    """生成月报摘要数据"""
    return {
        "journals_count": len(RAILWAY_JOURNALS_EN) + len(RAILWAY_JOURNALS_CN),
        "journals_en": RAILWAY_JOURNALS_EN,
        "journals_cn": RAILWAY_JOURNALS_CN,
        "wechat_accounts": WECHAT_ACCOUNTS,
        "industry_sites": INDUSTRY_SITES,
    }