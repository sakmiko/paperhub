"""arXiv 优化插件 — 超时控制 + 短期缓存，避免 arXiv API 慢请求阻塞"""
import time
from typing import Optional

from plugins import Plugin, register


class ArxivOptimizerPlugin(Plugin):
    name = "arxiv_optimizer"
    description = "arXiv API 超时优化 + 请求缓存，避免慢请求阻塞搜索"
    requires = []

    def setup(self, config: dict) -> None:
        super().setup(config)
        self._timeout = config.get("timeout", 15)
        self._cache_ttl = config.get("cache_ttl", 300)
        self._cache: dict = {}

    def search_platforms(self, query: str, limit: int, platforms: dict) -> Optional[list]:
        """拦截 arXiv 平台的搜索，使用更短的超时"""
        if "arxiv" not in platforms:
            return None

        cache_key = f"arxiv:{query}:{limit}"
        now = time.time()

        # 检查缓存
        if cache_key in self._cache:
            cached_time, cached_results = self._cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_results, []

        # 用短超时搜索
        arxiv = platforms["arxiv"]
        try:
            from core.utils import fetch
            import xml.etree.ElementTree as ET

            url = "https://export.arxiv.org/api/query"
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
            }
            resp = fetch(url, params=params, timeout=self._timeout, retries=1)
            if not resp or resp.status_code != 200:
                self._cache[cache_key] = (now, [])
                return [], []

            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            results = []
            from core.utils import PaperResult

            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""
                doi = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "doi":
                        doi = link.get("href", "").replace("http://dx.doi.org/", "")
                        break
                id_el = entry.find("atom:id", ns)
                url_val = id_el.text.strip() if id_el is not None else ""
                if not doi and url_val:
                    doi = url_val.replace("http://arxiv.org/abs/", "")
                summary_el = entry.find("atom:summary", ns)
                abstract = summary_el.text.strip()[:500] if summary_el is not None else ""
                published_el = entry.find("atom:published", ns)
                year = published_el.text[:4] if published_el is not None else ""
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_el = author.find("atom:name", ns)
                    if name_el is not None:
                        authors.append(name_el.text.strip())
                pdf_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href", "")
                        break
                results.append(PaperResult(
                    title=title,
                    authors=authors[:5],
                    doi=doi,
                    year=year,
                    url=url_val,
                    pdf_url=pdf_url,
                    abstract=abstract,
                    platform="arxiv",
                ))

            self._cache[cache_key] = (now, results)
            return results, []

        except Exception as e:
            self._cache[cache_key] = (now, [])
            return [], [f"[arxiv_optimizer]: {e}"]


register(ArxivOptimizerPlugin())
