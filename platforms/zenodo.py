"""Zenodo 平台"""
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class ZenodoPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "zenodo"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        url = "https://zenodo.org/api/records"
        params = {"q": query, "size": limit, "sort": "mostrecent"}
        if kwargs.get("type"):
            params["type"] = kwargs["type"]
        resp = fetch(url, params=params)
        if not resp:
            return []
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        return [self._parse_item(item) for item in hits if item]

    def _parse_item(self, item: dict) -> PaperResult:
        metadata = item.get("metadata", {}) or {}
        title = metadata.get("title", "")
        creators = metadata.get("creators", [])
        authors = [c.get("name", "") for c in creators if c.get("name")]
        doi = item.get("doi", "") or metadata.get("doi", "") or ""
        year = ""
        if metadata.get("publication_date"):
            year = metadata["publication_date"][:4]
        source = metadata.get("journal", "") or metadata.get("journal_title", "") or ""
        pdf_url = ""
        for f in item.get("files", []):
            if f.get("type") == "pdf" or f.get("key", "").endswith(".pdf"):
                pdf_url = f.get("links", {}).get("self", "") or f.get("download_url", "") or ""
                break
        abstract = metadata.get("description", "") or ""
        # Strip HTML tags from abstract
        if abstract:
            import re
            abstract = re.sub(r'<[^>]+>', '', abstract)[:500]
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi,
            year=year,
            source=source,
            url=item.get("links", {}).get("doi", "") or f"https://doi.org/{doi}" if doi else "",
            pdf_url=pdf_url,
            abstract=abstract,
            platform=self.name,
        )

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        url = f"https://zenodo.org/api/records"
        params = {"q": f"doi:{doi}", "size": 1}
        resp = fetch(url, params=params)
        if not resp:
            return None
        hits = resp.json().get("hits", {}).get("hits", [])
        return self._parse_item(hits[0]) if hits else None

    def download(self, paper: PaperResult) -> Optional[str]:
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "zenodo")
            if path:
                return str(path)
        return None