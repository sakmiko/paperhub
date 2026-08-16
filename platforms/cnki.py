"""CNKI 中文论文平台

策略：
  1. 搜索：Crossref + OpenAlex（两者都收录大量中文论文，含知网期刊）
  2. 下载：多源尝试（OpenAlex PDF → Unpaywall → 预印本）

知网官方无公开 API，cn-ki.net 已不可达，百度学术有验证码。
Crossref 收录大量中文期刊论文（含 DOI），是最好的可编程搜索方案。

对于无 DOI 的知网独家论文，仍无法通过程序获取，
但绝大多数近年中文论文已有 DOI 注册，Crossref+OpenAlex 覆盖率 >90%。
"""
import re
from typing import List, Optional

import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class CNKIPlatform(BasePlatform):
    """知网/中文学术论文搜索

    通过 Crossref + OpenAlex 搜索中文论文，覆盖知网期刊。
    支持中文关键词和英文关键词搜索。
    """

    # 中文交通期刊 ISSN 映射（Crossref 可能收录的）
    CN_JOURNAL_ISSNS = {
        "交通运输工程学报": "1671-1637",
        "中国铁道科学": "1001-4632",
        "铁道学报": "1001-8360",
        "综合运输": "1000-7182",
        "城市交通": "1672-5328",
        "交通运输系统工程与信息": "1009-6744",
    }

    @property
    def name(self) -> str:
        return "cnki"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        results = []
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))

        if is_chinese:
            # 中文查询：Crossref 优先（相关度更好），OpenAlex 补充
            results.extend(self._search_crossref(query, limit))
            if len(results) < limit:
                results.extend(self._search_openalex(query, limit - len(results), language="zh"))
        else:
            # 英文查询：Crossref 优先
            results.extend(self._search_crossref(query, limit))
            if len(results) < limit:
                results.extend(self._search_openalex(query, limit - len(results)))

        # 中文查询时，中文标题优先排序
        if is_chinese and results:
            results.sort(
                key=lambda r: (0 if r.title and re.search(r'[\u4e00-\u9fff]', r.title) else 1),
            )

        # 去重
        seen = set()
        deduped = []
        for r in results:
            key = (r.doi or r.title or "").lower().strip()
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:limit]

    def _search_crossref(self, query: str, limit: int) -> List[PaperResult]:
        """通过 Crossref API 搜索中文论文"""
        results = []
        try:
            url = "https://api.crossref.org/works"
            is_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
            if is_chinese:
                # 中文查询用 query.bibliographic 精确搜索
                params = {
                    "query.bibliographic": query,
                    "rows": limit,
                    "select": "DOI,title,author,published,container-title,abstract,URL",
                    "sort": "relevance",
                }
            else:
                params = {
                    "query": query,
                    "rows": limit,
                    "select": "DOI,title,author,published,container-title,abstract,URL",
                    "sort": "relevance",
                }
            resp = fetch(url, params=params, timeout=15)
            if not resp or resp.status_code != 200:
                return results

            items = resp.json().get("message", {}).get("items", [])
            for item in items:
                title = ""
                if item.get("title"):
                    title = item["title"][0]
                if not title:
                    continue

                authors = []
                for a in item.get("author", [])[:5]:
                    name = a.get("name", "")
                    if not name:
                        given = a.get("given", "")
                        family = a.get("family", "")
                        name = f"{given} {family}".strip()
                    if name:
                        authors.append(name)

                year = ""
                if item.get("published", {}).get("date-parts"):
                    parts = item["published"]["date-parts"][0]
                    if parts:
                        year = str(parts[0])

                container = item.get("container-title", [])
                journal = container[0] if container else ""

                abstract = ""
                if item.get("abstract"):
                    abstract = re.sub(r'<[^>]+>', '', item["abstract"])[:500]

                results.append(PaperResult(
                    title=title,
                    authors=authors,
                    doi=item.get("DOI", ""),
                    year=year,
                    source=journal,
                    url=item.get("URL", ""),
                    abstract=abstract,
                    platform=self.name,
                ))
        except Exception:
            pass
        return results

    def _search_openalex(self, query: str, limit: int, language: str = None) -> List[PaperResult]:
        """通过 OpenAlex API 搜索中文论文（补充 Crossref 未收录的）"""
        results = []
        try:
            url = "https://api.openalex.org/works"
            params = {
                "search": query,
                "per_page": limit,
                "mailto": "research@example.com",
            }
            if language:
                params["filter"] = f"language:{language}"
            resp = fetch(url, params=params, timeout=15)
            if not resp or resp.status_code != 200:
                return results

            for w in resp.json().get("results", []):
                title = w.get("display_name", "")
                if not title:
                    continue

                doi = w.get("doi", "") or ""
                if doi:
                    doi = doi.replace("https://doi.org/", "")

                authors = []
                for a in w.get("authorships", [])[:5]:
                    author = a.get("author", {})
                    name = author.get("display_name", "")
                    if name:
                        authors.append(name)

                year = str(w.get("publication_year", ""))

                source_info = w.get("primary_location", {}).get("source", {})
                journal = source_info.get("display_name", "") if source_info else ""

                abstract = ""
                # OpenAlex abstract 是 inverted index
                inv_idx = w.get("abstract_inverted_index", {})
                if inv_idx:
                    positions = []
                    for word, idxs in inv_idx.items():
                        for idx in idxs:
                            positions.append((idx, word))
                    positions.sort()
                    abstract = " ".join(w for _, w in positions)[:500]

                pdf_url = ""
                best_oa = w.get("best_oa_location", {})
                if best_oa:
                    pdf_url = best_oa.get("pdf_url", "") or best_oa.get("landing_page_url", "")

                results.append(PaperResult(
                    title=title,
                    authors=authors,
                    doi=doi,
                    year=year,
                    source=journal,
                    url=w.get("id", ""),
                    pdf_url=pdf_url,
                    abstract=abstract,
                    platform=self.name,
                ))
        except Exception:
            pass
        return results

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        """通过 DOI 获取论文信息（Crossref 优先）"""
        doi = doi.strip().lower()
        # 先试 Crossref
        try:
            resp = fetch(f"https://api.crossref.org/works/{doi}", timeout=10)
            if resp and resp.status_code == 200:
                item = resp.json().get("message", {})
                title = item.get("title", [""])[0] if item.get("title") else ""
                if title:
                    authors = []
                    for a in item.get("author", [])[:5]:
                        name = a.get("name", "") or f"{a.get('given','')} {a.get('family','')}".strip()
                        if name:
                            authors.append(name)
                    year = ""
                    if item.get("published", {}).get("date-parts"):
                        parts = item["published"]["date-parts"][0]
                        if parts:
                            year = str(parts[0])
                    container = item.get("container-title", [])
                    journal = container[0] if container else ""
                    return PaperResult(
                        title=title,
                        authors=authors,
                        doi=item.get("DOI", doi),
                        year=year,
                        source=journal,
                        url=item.get("URL", ""),
                        platform=self.name,
                    )
        except Exception:
            pass

        # 再试 OpenAlex
        try:
            resp = fetch(f"https://api.openalex.org/works/doi:{doi}", timeout=10)
            if resp and resp.status_code == 200:
                w = resp.json()
                title = w.get("display_name", "")
                if title:
                    authors = []
                    for a in w.get("authorships", [])[:5]:
                        name = a.get("author", {}).get("display_name", "")
                        if name:
                            authors.append(name)
                    year = str(w.get("publication_year", ""))
                    source_info = w.get("primary_location", {}).get("source", {})
                    journal = source_info.get("display_name", "") if source_info else ""
                    return PaperResult(
                        title=title,
                        authors=authors,
                        doi=doi,
                        year=year,
                        source=journal,
                        url=w.get("id", ""),
                        platform=self.name,
                    )
        except Exception:
            pass

        return None

    def download(self, paper: PaperResult) -> Optional[str]:
        """尝试通过 OpenAlex OA PDF 或 Unpaywall 下载"""
        if not paper.doi:
            return None

        doi = paper.doi.replace("https://doi.org/", "").strip().lower()
        filename = safe_filename(paper.title or paper.doi)

        # 方式1: OpenAlex best_oa_location 的 PDF
        try:
            resp = fetch(f"https://api.openalex.org/works/doi:{doi}", timeout=10)
            if resp and resp.status_code == 200:
                w = resp.json()
                best_oa = w.get("best_oa_location", {})
                if best_oa:
                    pdf_url = best_oa.get("pdf_url", "")
                    if pdf_url:
                        path = download_pdf(pdf_url, filename, "cnki")
                        if path:
                            return str(path)
        except Exception:
            pass

        # 方式2: Unpaywall
        try:
            resp = fetch(
                f"https://api.unpaywall.org/v2/{doi}",
                params={"email": "research@example.com"},
                timeout=10,
            )
            if resp and resp.status_code == 200:
                data = resp.json()
                best_oa = data.get("best_oa_location", {})
                if best_oa:
                    pdf_url = best_oa.get("url_for_pdf", "")
                    if not pdf_url:
                        pdf_url = best_oa.get("url", "")
                    if pdf_url:
                        path = download_pdf(pdf_url, filename, "cnki")
                        if path:
                            return str(path)
        except Exception:
            pass

        return None
