"""Google Scholar 搜索平台（通过公开页面解析）

注意：Google Scholar 有反爬机制，大量请求可能被屏蔽。
仅用于少量搜索，建议配合 --limit 使用。
"""
import re
import time
from typing import List, Optional
from urllib.parse import quote

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class GoogleScholarPlatform(BasePlatform):
    """Google Scholar 搜索（通过抓取公开页面）"""

    @property
    def name(self) -> str:
        return "google-scholar"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        url = f"https://scholar.google.com/scholar?q={quote(query)}&hl=en&as_sdt=0%2C5&num={min(limit, 20)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = fetch(url, headers=headers, timeout=15)
        if not resp:
            return []

        html = resp.text
        results = []
        # 提取论文条目
        entries = re.findall(r'<div[^>]*class="gs_ri"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
        for entry in entries[:limit]:
            title_match = re.search(r'<h3[^>]*class="gs_rt"[^>]*>.*?<a[^>]*>(.*?)</a>', entry, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""

            author_match = re.search(r'<div[^>]*class="gs_a"[^>]*>(.*?)</div>', entry, re.DOTALL)
            author_text = re.sub(r'<[^>]+>', '', author_match.group(1)).strip() if author_match else ""
            # 解析作者
            authors = [a.strip() for a in author_text.split("-")[0].split(",") if a.strip()][:5] if author_text else []

            # 提取年份
            year = ""
            year_match = re.search(r'(\d{4})', author_text)
            if year_match:
                year = year_match.group(1)

            # 提取摘要片段
            snippet_match = re.search(r'<div[^>]*class="gs_rs"[^>]*>(.*?)</div>', entry, re.DOTALL)
            abstract = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""

            # 提取链接
            link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', entry, re.DOTALL)
            url_link = link_match.group(1) if link_match else ""

            results.append(PaperResult(
                title=title,
                authors=authors,
                year=year,
                source="Google Scholar",
                url=url_link,
                abstract=abstract[:500],
                platform=self.name,
            ))

        return results

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        """通过 DOI 搜索"""
        results = self.search(doi, limit=1)
        return results[0] if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        """Google Scholar 不直接提供下载"""
        return None