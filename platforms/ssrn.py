"""SSRN (Social Science Research Network) 平台"""
import re
from typing import List, Optional
from urllib.parse import quote

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class SSRNPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "ssrn"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        url = f"https://papers.ssrn.com/sol3/DisplayAbstractSearch.cfm?search={quote(query)}&pageSize={limit}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = fetch(url, headers=headers, timeout=15)
        if not resp:
            return []

        html = resp.text
        results = []
        # 提取论文条目
        entries = re.findall(r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>', html, re.DOTALL)
        for entry in entries[:limit]:
            title_area = entry[0] if len(entry) > 0 else ""
            title_match = re.search(r'<a[^>]*>(.*?)</a>', title_area, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""

            author_area = entry[1] if len(entry) > 1 else ""
            authors = [a.strip() for a in author_area.split(";") if a.strip()][:5]

            link_match = re.search(r'href="([^"]+)"', title_area)
            url_link = f"https://papers.ssrn.com{link_match.group(1)}" if link_match else ""

            if title:
                results.append(PaperResult(
                    title=title,
                    authors=authors,
                    source="SSRN",
                    url=url_link,
                    platform=self.name,
                ))
        return results

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        results = self.search(doi, limit=1)
        return results[0] if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        if paper.url and "ssrn.com" in paper.url:
            # SSRN 论文有直接下载链接
            dl_url = paper.url.replace("abstract=", "delivery.cfm/")
            path = download_pdf(dl_url, safe_filename(paper.title), "ssrn")
            if path:
                return str(path)
        return None