"""交通领域期刊搜索增强模块

支持按期刊过滤、模糊搜索交通领域论文。
集成到 CLI 使用 --transport 或 --transport-journal 参数。
"""
import re
from typing import List, Optional

# ===== 交通领域核心期刊列表 =====
# 格式: (期刊名关键词, 全称, 缩写, ISSN)
TRANSPORT_JOURNALS = [
    # === Transportation Research Board (TRB) 系列 ===
    ("Transportation Research Record", "Transportation Research Record: Journal of the Transportation Research Board", "TRR", "0361-1981"),
    ("Transportation Research Part A", "Transportation Research Part A: Policy and Practice", "TR-A", "0965-8564"),
    ("Transportation Research Part B", "Transportation Research Part B: Methodological", "TR-B", "0191-2615"),
    ("Transportation Research Part C", "Transportation Research Part C: Emerging Technologies", "TR-C", "0968-090X"),
    ("Transportation Research Part D", "Transportation Research Part D: Transport and Environment", "TR-D", "1361-9209"),
    ("Transportation Research Part E", "Transportation Research Part E: Logistics and Transportation Review", "TR-E", "1366-5545"),
    ("Transportation Research Part F", "Transportation Research Part F: Traffic Psychology and Behaviour", "TR-F", "1369-8478"),
    ("Transportation Research Interdisciplinary Perspectives", "Transportation Research Interdisciplinary Perspectives", "TRIP", "2590-1982"),
    ("Transportation Research Procedia", "Transportation Research Procedia", "TR-Procedia", "2352-1465"),
    ("Transportation Research Today", "Transportation Research Today", "TR Today", "3051-360X"),

    # === INFORMS 期刊 ===
    ("Transportation Science", "Transportation Science", "Trans. Sci.", "0041-1655"),

    # === Elsevier 交通期刊 ===
    ("Journal of Transport Geography", "Journal of Transport Geography", "J. Transp. Geogr.", "0966-6923"),
    ("Transport Policy", "Transport Policy", "Transp. Policy", "0967-070X"),
    ("Transportation", "Transportation", "Transportation", "0049-4488"),
    ("Case Studies on Transport Policy", "Case Studies on Transport Policy", "CSTP", "2213-624X"),
    ("Journal of Air Transport Management", "Journal of Air Transport Management", "J. Air Transp. Manag.", "0969-6997"),
    ("Research in Transportation Economics", "Research in Transportation Economics", "RTE", "0739-8859"),
    ("Research in Transportation Business & Management", "Research in Transportation Business & Management", "RTBM", "2210-5395"),
    ("Transportation Research Part A: Policy and Practice", "Transportation Research Part A: Policy and Practice", "TR-A", "0965-8564"),

    # === Taylor & Francis 交通期刊 ===
    ("Transportmetrica A", "Transportmetrica A: Transport Science", "Transportmetrica A", "2324-9935"),
    ("Transportmetrica B", "Transportmetrica B: Transport Dynamics", "Transportmetrica B", "2168-0566"),
    ("Transportation Letters", "Transportation Letters: The International Journal of Transportation Research", "Transp. Lett.", "1942-7867"),
    ("International Journal of Sustainable Transportation", "International Journal of Sustainable Transportation", "IJST", "1556-8318"),
    ("Journal of Intelligent Transportation Systems", "Journal of Intelligent Transportation Systems", "JITS", "1547-2450"),
    ("Transportation Planning and Technology", "Transportation Planning and Technology", "Transp. Plan. Technol.", "0308-1060"),
    ("Maritime Policy & Management", "Maritime Policy & Management", "Marit. Policy Manag.", "0308-8839"),
    ("Transport Reviews", "Transport Reviews", "Transp. Rev.", "0144-1647"),
    ("Transportation Safety and Environment", "Transportation Safety and Environment", "TSE", "2631-4428"),

    # === IEEE / 工程技术类 ===
    ("IEEE Transactions on Intelligent Transportation Systems", "IEEE Transactions on Intelligent Transportation Systems", "IEEE T-ITS", "1524-9050"),
    ("IEEE Intelligent Transportation Systems Magazine", "IEEE Intelligent Transportation Systems Magazine", "IEEE ITS Mag.", "1939-1390"),
    ("IEEE Transactions on Vehicular Technology", "IEEE Transactions on Vehicular Technology", "IEEE TVT", "0018-9545"),
    ("Journal of Advanced Transportation", "Journal of Advanced Transportation", "J. Adv. Transp.", "0197-6729"),
    ("IET Intelligent Transport Systems", "IET Intelligent Transport Systems", "IET ITS", "1751-956X"),

    # === 安全/事故类 ===
    ("Accident Analysis & Prevention", "Accident Analysis & Prevention", "AAP", "0001-4575"),
    ("Journal of Safety Research", "Journal of Safety Research", "J. Safety Res.", "0022-4375"),
    ("Journal of Transportation Safety & Security", "Journal of Transportation Safety & Security", "JTSS", "1943-9962"),
    ("Traffic Injury Prevention", "Traffic Injury Prevention", "Traffic Inj. Prev.", "1538-9588"),

    # === 交通工程/土木 ===
    ("Journal of Transportation Engineering", "Journal of Transportation Engineering, Part A: Systems", "JTE", "0733-947X"),
    ("Journal of Transportation Engineering, Part B: Pavements", "Journal of Transportation Engineering, Part B: Pavements", "JTE-B", "2573-5438"),
    ("Canadian Journal of Civil Engineering", "Canadian Journal of Civil Engineering", "Can. J. Civ. Eng.", "0315-1468"),
    ("KSCE Journal of Civil Engineering", "KSCE Journal of Civil Engineering", "KSCE J. Civ. Eng.", "1226-7988"),

    # === 公共交通/共享出行 ===
    ("Public Transport", "Public Transport", "Public Transp.", "1866-749X"),
    ("Journal of Public Transportation", "Journal of Public Transportation", "J. Public Transp.", "1077-291X"),
    ("Transportation Research Part C: Emerging Technologies", "Transportation Research Part C: Emerging Technologies", "TR-C", "0968-090X"),

    # === 新兴/跨学科 ===
    ("eTransportation", "eTransportation", "eTransportation", "2590-1168"),
    ("Communications in Transportation Research", "Communications in Transportation Research", "Commun. Transp. Res.", "2097-0505"),
    ("npj Sustainable Mobility and Transport", "npj Sustainable Mobility and Transport", "npj Sustain. Mobil.", "3004-8664"),
    ("Digital Transportation and Safety", "Digital Transportation and Safety", "DTS", "2994-6301"),
    ("European Transport Research Review", "European Transport Research Review", "ETRR", "1867-0717"),
    ("European Journal of Transport and Infrastructure Research", "European Journal of Transport and Infrastructure Research", "EJTIR", "1567-7133"),
    ("EURO Journal on Transportation and Logistics", "EURO Journal on Transportation and Logistics", "EURO JTL", "2192-4376"),
    ("The Open Transportation Journal", "The Open Transportation Journal", "Open Transp. J.", "1874-4478"),
    ("Journal of Transport and Land Use", "Journal of Transport and Land Use", "JTLU", "1938-7849"),
    ("Transportation in Developing Economies", "Transportation in Developing Economies", "Transp. Dev. Econ.", "2364-7247"),
    ("International Journal of Transportation Science and Technology", "International Journal of Transportation Science and Technology", "IJTST", "2046-0430"),
    ("Journal of Rail Transport Planning & Management", "Journal of Rail Transport Planning & Management", "JRTPM", "2210-9706"),
    ("Asian Transport Studies", "Asian Transport Studies", "ATS", "2185-5560"),
    ("Transportation Research Part C: Emerging Technologies", "Transportation Research Part C: Emerging Technologies", "TR-C", "0968-090X"),

    # === 中文交通期刊 ===
    ("中国公路学报", "中国公路学报", "China J. Highway Transp.", "1001-7372"),
    ("交通运输工程学报", "交通运输工程学报", "J. Traffic Transp. Eng.", "1671-1637"),
    ("交通运输系统工程与信息", "交通运输系统工程与信息", "J. Transp. Syst. Eng. Inf. Technol.", "1009-6744"),
    ("公路交通科技", "公路交通科技", "J. Highway Transp. Res. Dev.", "1002-0268"),
    ("城市交通", "城市交通", "Urban Transport of China", "1672-5328"),
    ("交通信息与安全", "交通信息与安全", "J. Transp. Inf. Saf.", "1674-4861"),
    ("交通工程", "交通工程", "J. Transp. Eng.", "2096-3432"),
    ("综合运输", "综合运输", "Compr. Transp.", "1000-713X"),
    ("铁道学报", "铁道学报", "J. China Railway Soc.", "1001-8360"),
    ("铁道科学与工程学报", "铁道科学与工程学报", "J. Railway Sci. Eng.", "1672-7029"),
    ("城市轨道交通研究", "城市轨道交通研究", "Urban Mass Transit", "1007-869X"),
    ("交通科学与工程", "交通科学与工程", "J. Transp. Sci. Eng.", "1674-599X"),
    ("武汉理工大学学报（交通科学与工程版）", "武汉理工大学学报（交通科学与工程版）", "J. Wuhan Univ. Technol. (Transp. Sci. Eng.)", "2095-3844"),
    ("现代交通技术", "现代交通技术", "Mod. Transp. Technol.", "1672-9889"),
    ("交通节能与环保", "交通节能与环保", "Transp. Energy Conserv. Environ.", "1673-6478"),
]

# 构建搜索关键词（用于 Crossref filter）
JOURNAL_KEYWORDS = sorted(set(j[0] for j in TRANSPORT_JOURNALS))


def fuzzy_match_journal(query: str, threshold: float = 0.4) -> List[str]:
    """模糊匹配期刊名称，返回匹配的期刊名称列表"""
    query = query.lower().strip()
    if not query:
        return []

    matches = []
    for name, full, abbr, issn in TRANSPORT_JOURNALS:
        # 精确匹配
        if query in name.lower() or query in full.lower() or query.lower() == abbr.lower():
            matches.append((name, 1.0))
            continue
        # 词组匹配
        query_words = set(re.findall(r'\w+', query))
        name_words = set(re.findall(r'\w+', name.lower()))
        if not query_words or not name_words:
            continue
        overlap = len(query_words & name_words)
        ratio = overlap / max(len(query_words), len(name_words))
        if ratio >= threshold:
            matches.append((name, ratio))
        # 缩写匹配
        if abbr and query.lower() in abbr.lower():
            matches.append((name, 0.8))

    # 按匹配度排序去重
    matches.sort(key=lambda x: -x[1])
    seen = set()
    unique = []
    for name, score in matches:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def get_filter_params(journal_name: str) -> dict:
    """获取 Crossref 过滤器参数"""
    return {"filter": f"container-title:{journal_name}"}


def get_all_journals() -> List[dict]:
    """获取所有期刊信息"""
    return [
        {"name": name, "full_name": full, "abbreviation": abbr, "issn": issn}
        for name, full, abbr, issn in TRANSPORT_JOURNALS
    ]


def search_transport(query: str, journal: str = None, limit: int = 10) -> List[dict]:
    """搜索交通领域论文

    通过 Crossref 按期刊过滤搜索。
    journal 参数可以是期刊名关键词或缩写，自动模糊匹配。
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from core.utils import fetch, PaperResult

    # 确定期刊过滤
    if journal:
        matched = fuzzy_match_journal(journal)
        if not matched:
            return []
        journals_to_search = matched[:3]  # 最多查3个匹配期刊
    else:
        # 无指定期刊时，搜索主要交通期刊
        journals_to_search = [
            "Transportation Research Part A",
            "Transportation Research Part B",
            "Transportation Research Part C",
            "Transportation Research Record",
            "Transportation Science",
            "Transportation",
            "Journal of Transport Geography",
            "Transport Policy",
            "Accident Analysis & Prevention",
            "IEEE Transactions on Intelligent Transportation Systems",
            "Transportmetrica A",
            "Journal of Advanced Transportation",
            "Transportation Letters",
            "International Journal of Sustainable Transportation",
            "Public Transport",
            "Journal of Intelligent Transportation Systems",
        ]

    url = "https://api.crossref.org/works"
    results = []
    if journals_to_search:
        for jname in journals_to_search:
            params = {"query": query, "filter": f"container-title:{jname}", "rows": limit // len(journals_to_search) + 1}
            resp = fetch(url, params=params, timeout=15)
            if not resp:
                continue
            try:
                items = resp.json().get("message", {}).get("items", [])
            except Exception:
                continue
            for item in items:
                title = (item.get("title") or [""])[0]
                if not title:
                    continue
                authors = []
                for a in item.get("author", []):
                    name = " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
                    if name:
                        authors.append(name)
                doi = item.get("DOI", "") or ""
                year = ""
                for df in ["published-print", "published-online", "created", "issued"]:
                    parts = item.get(df, {}).get("date-parts", [[]])[0]
                    if parts:
                        year = str(parts[0])
                        break
                results.append({
                    "title": title,
                    "authors": authors[:5],
                    "doi": doi,
                    "year": year,
                    "journal": item.get("container-title", [""])[0] if item.get("container-title") else jname,
                    "url": f"https://doi.org/{doi}" if doi else "",
                    "platform": "crossref",
                })
                if len(results) >= limit:
                    return results
    return results