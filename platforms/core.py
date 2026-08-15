"""CORE 平台（开放获取论文聚合）

CORE API v3 需要免费注册获取 API Key: https://core.ac.uk/services/api

配置方式：
  1. 环境变量: CORE_API_KEY=your_key
  2. 或直接修改下方 API_KEY 变量

无 Key 时尝试通过公共搜索接口获取数据。
"""
import os
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


API_KEY = os.environ.get("CORE_API_KEY", "")
API_BASE = "https://api.core.ac.uk/v3"


class COREPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "core"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        if API_KEY:
            return self._search_api(query, limit)
        return self._search_nokey(query, limit)

    def _search_api(self, query: str, limit: int) -> List[PaperResult]:
        url = f"{API_BASE}/search/works"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        params = {"q": query, "pageSize": min(limit, 100), "page": 1}
        resp = fetch(url, params=params, headers=headers)
        if not resp:
            return []
        data = resp.json()
        results = data.get("results", [])
        return [self._parse_item(item) for item in results if item]

    def _search_nokey(self, query: str, limit: int) -> List[PaperResult]:
        """无 Key 时使用 CORE 公开搜索页面"""
        url = "https://core.ac.uk/search"
        params = {"q": query, "page": 1}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = fetch(url, params=params, headers=headers)
        if not resp:
            return []
        from html.parser import HTMLParser
        html = resp.text
        results = []
        # 简单的 HTML 解析提取论文标题和链接
        import re
        titles = re.findall(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
        links = re.findall(r'<a[^>]*href="(/display/\d+)"[^>]*>', html)
        for i, (title, link) in enumerate(zip(titles, links)):
            if i >= limit:
                break
            title = re.sub(r'<[^>]+>', '', title).strip()
            full_url = f"https://core.ac.uk{link}" if link.startswith("/") else link
            results.append(PaperResult(
                title=title,
                url=full_url,
                platform=self.name,
            ))
        return results

    def _parse_item(self, item: dict) -> PaperResult:
        title = item.get("title", "")
        authors = [c.get("name", "") for c in item.get("contributors", []) if c.get("name")]
        doi = item.get("doi", "") or ""
        year = str(item.get("yearPublished", "")) or str(item.get("datePublished", ""))[:4]
        source = item.get("publisher", "") or item.get("journalName", "") or ""
        pdf_url = ""
        for id_ in item.get("identifiers", []):
            if ".pdf" in id_ or id_.startswith("http"):
                pdf_url = id_
                break
        if not pdf_url and item.get("fullTextIdentifier"):
            pdf_url = item["fullTextIdentifier"][0] if isinstance(item["fullTextIdentifier"], list) else item["fullTextIdentifier"]
        abstract = item.get("abstract", "") or ""
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi,
            year=year,
            source=source,
            url=item.get("sourceUrl", "") or "",
            pdf_url=pdf_url,
            abstract=abstract[:500],
            platform=self.name,
        )

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        if not API_KEY:
            return None
        url = f"{API_BASE}/search/works"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        params = {"q": doi, "pageSize": 1}
        resp = fetch(url, params=params, headers=headers)
        if not resp:
            return None
        results = resp.json().get("results", [])
        return self._parse_item(results[0]) if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "core")
            if path:
                return str(path)
        return None