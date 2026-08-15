"""PubMed Central 平台"""
import re
import time
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class PubMedPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "pubmed"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        """通过 PubMed E-utilities 搜索论文"""
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pmc", "term": query, "retmax": limit, "retmode": "json"}
        resp = fetch(url, params=params)
        if not resp:
            return []

        data = resp.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # 获取详细信息
        return self._fetch_details(id_list)

    def _fetch_details(self, id_list: List[str]) -> List[PaperResult]:
        """获取论文详细信息"""
        ids = ",".join(id_list)
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        params = {"db": "pmc", "id": ids, "retmode": "json"}
        resp = fetch(url, params=params)
        if not resp:
            return []

        data = resp.json()
        results = data.get("result", {})
        results_list = []
        for uid in id_list:
            item = results.get(uid)
            if not item:
                continue
            title = item.get("title", "")
            authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
            source = item.get("source", "")
            pubdate = item.get("pubdate", "")
            doi = ""
            for aid in item.get("articleids", []):
                if aid.get("idtype") == "doi":
                    doi = aid.get("value", "")
                    break
            pmcid = item.get("uid", "")
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/" if pmcid else ""
            result = PaperResult(
                title=title,
                authors=authors[:5],
                doi=doi,
                year=pubdate[:4],
                source=source,
                url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/" if pmcid else "",
                pdf_url=pdf_url,
                abstract=item.get("elocationid", ""),
                platform=self.name,
            )
            results_list.append(result)
        return results_list

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        """按 DOI 获取论文"""
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pmc", "term": f"{doi}[doi]", "retmax": 1, "retmode": "json"}
        resp = fetch(url, params=params)
        if not resp:
            return None

        data = resp.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return None

        results = self._fetch_details(id_list)
        return results[0] if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        """下载 PDF"""
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "pubmed")
            return str(path) if path else None
        return None