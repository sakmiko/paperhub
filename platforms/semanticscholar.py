"""Semantic Scholar 平台"""
import time
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class SemanticScholarPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "semantic-scholar"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": "title,authors,externalIds,year,venue,abstract,url,openAccessPdf",
        }
        # 首次尝试
        result = self._try_search(url, params)
        if result is not None:
            return result
        # 429 时等待后重试
        time.sleep(10)
        result = self._try_search(url, params)
        return result or []

    def _try_search(self, url: str, params: dict) -> Optional[List[PaperResult]]:
        resp = fetch(url, params=params, timeout=20)
        if not resp:
            return None
        if resp.status_code == 429:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        results = data.get("data", []) or data.get("results", [])
        return [self._parse_item(item) for item in results if item]

    def _parse_item(self, item: dict) -> PaperResult:
        title = item.get("title", "")
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        ext_ids = item.get("externalIds", {}) or {}
        doi = ext_ids.get("DOI", "")
        year = str(item.get("year", ""))
        pdf_info = item.get("openAccessPdf", {}) or {}
        pdf_url = pdf_info.get("url", "") if pdf_info else ""
        abstract = item.get("abstract", "") or ""
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi,
            year=year,
            source=item.get("venue", ""),
            url=item.get("url", ""),
            pdf_url=pdf_url,
            abstract=abstract[:500],
            platform=self.name,
        )

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        params = {"fields": "title,authors,externalIds,year,venue,abstract,url,openAccessPdf"}
        for attempt in range(3):
            resp = fetch(url, params=params, timeout=20)
            if not resp:
                time.sleep(5)
                continue
            if resp.status_code == 429:
                time.sleep(10)
                continue
            if resp.status_code != 200:
                return None
            try:
                return self._parse_item(resp.json())
            except Exception:
                return None
        return None

    def download(self, paper: PaperResult) -> Optional[str]:
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "semantic-scholar")
            if path:
                return str(path)
        # 无 OA PDF 时尝试通过 DOI 走 Sci-Hub
        if paper.doi:
            from .scidb import SciHubPlatform
            return SciHubPlatform().download(paper)
        return None