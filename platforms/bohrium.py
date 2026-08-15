"""玻尔 (Bohrium) 科学导航平台

Bohrium (https://www.bohrium.com) 是深势科技打造的 AI for Science 科研平台。
涵盖 1.6亿+ 论文、1.6亿+ 专利，支持语义搜索、智能问答。

需要 API Key 或在机构网络内（CARSI/SSO）使用。
配置方式：
  1. 环境变量: BOHRIUM_API_KEY=your_key
  2. 或直接传入 api_key 参数
"""
import json
import os
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


# 默认 API 端点
API_BASE = "https://www.bohrium.com"
API_SEARCH = f"{API_BASE}/api/v1/search"
API_QNA = f"{API_BASE}/api/v1/qna"
API_STATUS = f"{API_BASE}/api/v1/status"


class BohriumPlatform(BasePlatform):
    """玻尔科学导航平台"""

    def __init__(self, api_key: str = None):
        self._api_key = api_key or os.environ.get("BOHRIUM_API_KEY", "")

    @property
    def name(self) -> str:
        return "bohrium"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        """通过玻尔科学导航搜索论文

        使用 GET 搜索（不需要 API Key 也能获取公开搜索结果）
        或 POST 搜索（需要 API Key，支持语义搜索）
        """
        results = []
        # 尝试 POST 搜索（需要 API Key）
        if self._api_key:
            results = self._search_post(query, limit)
        if not results:
            # 回退到无 API Key 模式（通过页面搜索）
            results = self._search_public(query, limit)
        return results

    def _search_post(self, query: str, limit: int) -> List[PaperResult]:
        """使用 API Key 进行语义搜索"""
        try:
            payload = {"query": query, "limit": limit, "model": "auto"}
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            import requests
            resp = requests.post(API_SEARCH, json=payload, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []
            data = resp.json()
            papers = data.get("papers", []) or data.get("results", []) or []
            return [self._parse_item(p) for p in papers if p]
        except Exception:
            return []

    def _search_public(self, query: str, limit: int) -> List[PaperResult]:
        """通过公开页面搜索"""
        try:
            import requests
            # 使用玻尔科学导航的公开搜索 API
            url = f"{API_BASE}/next-api/search"
            params = {"q": query, "page": 1, "size": limit}
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []
            data = resp.json()
            items = data.get("data", []) or data.get("items", []) or data.get("results", []) or []
            return [self._parse_item_public(item) for item in items if item]
        except Exception:
            return []

    def _parse_item(self, item: dict) -> PaperResult:
        """解析 API 返回的论文数据"""
        title = item.get("title", "") or item.get("paper_title", "") or ""
        authors = []
        for a in item.get("authors", []) or item.get("authors_list", []) or []:
            if isinstance(a, str):
                authors.append(a)
            elif isinstance(a, dict):
                authors.append(a.get("name", "") or a.get("full_name", ""))
        doi = item.get("doi", "") or ""
        year = str(item.get("year", "") or item.get("publication_year", ""))
        source = item.get("journal", "") or item.get("journal_name", "") or ""
        abstract = item.get("abstract", "") or item.get("paper_abstract", "") or ""
        pdf_url = item.get("pdf_url", "") or item.get("full_text_url", "") or ""
        url = item.get("url", "") or item.get("paper_url", "") or item.get("source_url", "") or ""
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi,
            year=year,
            source=source,
            url=url,
            pdf_url=pdf_url,
            abstract=abstract[:500],
            platform=self.name,
        )

    def _parse_item_public(self, item: dict) -> PaperResult:
        """解析公开搜索返回的论文数据"""
        return self._parse_item(item)

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        """按 DOI 搜索"""
        if not doi:
            return None
        results = self.search(doi, limit=1)
        return results[0] if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        """尝试下载"""
        if paper.pdf_url:
            path = download_pdf(paper.pdf_url, safe_filename(paper.title), "bohrium")
            if path:
                return str(path)
        # 尝试通过 DOI 在 Sci-Hub 下载
        if paper.doi:
            from .scidb import SciHubPlatform
            sh = SciHubPlatform()
            return sh.download(paper)
        return None