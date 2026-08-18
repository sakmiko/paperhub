"""Nature.com PDF链接提取适配器"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from platforms.publisher_adapters import BaseAdapter


class NatureAdapter(BaseAdapter):
    def can_handle(self, url: str) -> bool:
        return "nature.com" in url.lower()

    def extract_pdf_url(self, html: str, url: str = ""):
        soup = BeautifulSoup(html, "html.parser")
        # 1. citation_pdf_url meta tag
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])
        # 2. Nature pattern: /articles/XXXX → /articles/XXXX.pdf
        m = re.search(r"/articles/([a-z0-9-]+)", url, re.I)
        if m:
            return f"https://www.nature.com/articles/{m.group(1)}.pdf"
        # 3. Find PDF link in page
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf") and "article" in href.lower():
                return urljoin(url, href)
        return None
