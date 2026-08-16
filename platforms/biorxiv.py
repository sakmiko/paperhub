"""bioRxiv/medRxiv 平台（通过 Crossref API 查询）"""
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class BiorxivPlatform(BasePlatform):
    """bioRxiv/medRxiv 预印本查询

    通过 Crossref API 搜索 bioRxiv/medRxiv 论文。
    bioRxiv 原生 API 不稳定，改用 Crossref 查询。
    """

    @property
    def name(self) -> str:
        return "biorxiv"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        results = []
        for server in ["bioRxiv", "medRxiv"]:
            url = "https://api.crossref.org/works"
            params = {
                "query": query,
                "filter": f"container-title:{server}",
                "rows": limit // 2 + 1,
            }
            resp = fetch(url, params=params, timeout=15)
            if not resp or resp.status_code != 200:
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
                for date_field in ["published-print", "published-online", "created", "issued"]:
                    parts = item.get(date_field, {}).get("date-parts", [[]])[0]
                    if parts:
                        year = str(parts[0])
                        break
                # bioRxiv PDF URL pattern
                pdf_url = ""
                if "10.1101" in doi:
                    doi_suffix = doi.replace("10.1101/", "")
                    pdf_url = f"https://www.biorxiv.org/content/10.1101/{doi_suffix}.full.pdf"
                result = PaperResult(
                    title=title,
                    authors=authors[:5],
                    doi=doi,
                    year=year,
                    source=server,
                    url=item.get("URL", "") or f"https://doi.org/{doi}",
                    pdf_url=pdf_url,
                    platform=self.name,
                )
                results.append(result)
                if len(results) >= limit:
                    return results
        return results

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        # 通过 Crossref 查询
        doi_clean = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
        url = f"https://api.crossref.org/works/{doi_clean}"
        resp = fetch(url, timeout=15)
        if not resp or resp.status_code != 200:
            return None
        try:
            item = resp.json().get("message", {})
        except Exception:
            return None
        title = (item.get("title") or [""])[0]
        if not title:
            return None
        authors = []
        for a in item.get("author", []):
            name = " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
            if name:
                authors.append(name)
        year = ""
        for date_field in ["published-print", "published-online", "created", "issued"]:
            parts = item.get(date_field, {}).get("date-parts", [[]])[0]
            if parts:
                year = str(parts[0])
                break
        container = item.get("container-title", [""])
        source = container[0] if container else ""
        pdf_url = ""
        if "10.1101" in doi_clean:
            doi_suffix = doi_clean.replace("10.1101/", "")
            pdf_url = f"https://www.biorxiv.org/content/10.1101/{doi_suffix}.full.pdf"
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi_clean,
            year=year,
            source=source,
            url=f"https://doi.org/{doi_clean}",
            pdf_url=pdf_url,
            platform=self.name,
        )

    def download(self, paper: PaperResult) -> Optional[str]:
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "biorxiv")
            if path:
                return str(path)
        # 兜底通过 Sci-Hub
        if paper.doi:
            from .scidb import SciHubPlatform
            return SciHubPlatform().download(paper)
        return None