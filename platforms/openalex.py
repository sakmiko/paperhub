"""OpenAlex 平台"""
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class OpenAlexPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "openalex"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        """通过 OpenAlex API 搜索"""
        url = "https://api.openalex.org/works"
        params = {"search": query, "per_page": limit}
        if kwargs.get("year"):
            params["filter"] = f"publication_year:{kwargs['year']}"
        if kwargs.get("author"):
            params["filter"] = f"authorships.author.display_name:{kwargs['author']}"
        resp = fetch(url, params=params)
        if not resp:
            return []
        data = resp.json()
        results = data.get("results", [])
        return [self._parse_item(item) for item in results if item]

    def _parse_item(self, item: dict) -> PaperResult:
        title = item.get("title", "")
        authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", []) if a.get("author")]
        doi = item.get("doi", "").replace("https://doi.org/", "") if item.get("doi") else ""
        year = str(item.get("publication_year", ""))
        source = item.get("primary_location", {}).get("source", {}).get("display_name", "") if item.get("primary_location") else ""
        open_access = item.get("open_access", {})
        pdf_url = open_access.get("oa_url", "") if open_access.get("is_oa") else ""
        abstract = item.get("abstract_inverted_index", "")
        # Convert inverted index to plain text
        if isinstance(abstract, dict):
            words = []
            for word, positions in abstract.items():
                for pos in positions:
                    words.append((pos, word))
            abstract = " ".join(w for _, w in sorted(words))[:500]
        else:
            abstract = str(abstract)[:500] if abstract else ""
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi,
            year=year,
            source=source,
            url=f"https://doi.org/{doi}" if doi else "",
            pdf_url=pdf_url or "",
            abstract=abstract,
            platform=self.name,
        )

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        url = f"https://api.openalex.org/works/doi:{doi}"
        resp = fetch(url)
        if not resp or resp.status_code != 200:
            return None
        return self._parse_item(resp.json())

    def download(self, paper: PaperResult) -> Optional[str]:
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "openalex")
            if path:
                return str(path)
        return None