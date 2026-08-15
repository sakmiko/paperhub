"""Crossref 平台"""
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class CrossrefPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "crossref"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        """通过 Crossref API 搜索论文"""
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": min(limit, 100)}
        resp = fetch(url, params=params)
        if not resp:
            return []

        data = resp.json()
        items = data.get("message", {}).get("items", [])
        return [self._parse_item(item) for item in items if item]

    def _parse_item(self, item: dict) -> PaperResult:
        title = (item.get("title") or [""])[0]
        authors = []
        for a in item.get("author", []):
            name = " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
            if name:
                authors.append(name)
        doi = item.get("DOI", "")
        year = ""
        for date_field in ["published-print", "published-online", "created", "issued", "deposited"]:
            parts = item.get(date_field, {}).get("date-parts", [[]])[0]
            if parts:
                year = str(parts[0])
                break
        source = item.get("publisher", "") or item.get("container-title", [""])[0] if item.get("container-title") else ""
        abstract = item.get("abstract", "") or ""
        url = f"https://doi.org/{doi}" if doi else ""
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi,
            year=year,
            source=source,
            url=url,
            abstract=abstract[:500] if abstract else "",
            platform=self.name,
        )

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        url = f"https://api.crossref.org/works/{doi}"
        resp = fetch(url)
        if not resp or resp.status_code != 200:
            return None
        item = resp.json().get("message", {})
        return self._parse_item(item)

    def download(self, paper: PaperResult) -> Optional[str]:
        """Crossref 只做元数据，下载交给其他平台"""
        return None