"""DOAJ (Directory of Open Access Journals) 平台"""
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class DOAJPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "doaj"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        """DOAJ API v2 搜索

        端点格式: /api/v2/search/articles/QUERY
        query 作为路径参数，pageSize 作为查询参数
        """
        import requests
        url = f"https://doaj.org/api/v2/search/articles/{requests.utils.quote(query)}"
        params = {"pageSize": min(limit, 100), "page": 1}
        resp = fetch(url, params=params, timeout=15)
        if not resp or resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except Exception:
            return []
        results = data.get("results", [])
        return [self._parse_item(item) for item in results if item]

    def _parse_item(self, item: dict) -> PaperResult:
        bibjson = item.get("bibjson", {}) or {}
        title = bibjson.get("title", "")
        authors = [a.get("name", "") for a in bibjson.get("author", []) if a.get("name")]
        doi = ""
        for id_ in bibjson.get("identifier", []):
            if id_.get("type") == "doi":
                doi = id_.get("id", "")
                break
        year = str(bibjson.get("year", ""))
        journal = bibjson.get("journal", {}) or {}
        source = journal.get("name", "") or journal.get("title", "") or ""
        pdf_url = ""
        for link in bibjson.get("link", []):
            if link.get("content_type", "").lower().find("pdf") >= 0 and link.get("url"):
                pdf_url = link["url"]
                break
        if not pdf_url and bibjson.get("link"):
            pdf_url = bibjson["link"][0].get("url", "")
        abstract = bibjson.get("abstract", "") or ""
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi,
            year=year,
            source=source,
            url=pdf_url or "",
            pdf_url=pdf_url,
            abstract=abstract[:500],
            platform=self.name,
        )

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        import requests
        url = f"https://doaj.org/api/v2/search/articles/{requests.utils.quote(doi)}"
        params = {"pageSize": 1}
        resp = fetch(url, params=params, timeout=15)
        if not resp:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        results = data.get("results", [])
        return self._parse_item(results[0]) if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "doaj")
            if path:
                return str(path)
        return None