"""Springer Link PDF链接提取适配器"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from platforms.publisher_adapters import BaseAdapter


class SpringerAdapter(BaseAdapter):
    def can_handle(self, url: str) -> bool:
        return "springer.com" in url.lower() or "link.springer.com" in url.lower()

    def extract_pdf_url(self, html: str, url: str = ""):
        soup = BeautifulSoup(html, "html.parser")
        # 1. citation_pdf_url meta tag
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])
        # 2. Springer pattern: /article/10.1007/xxx → /content/pdf/10.1007/xxx.pdf
        m = re.search(r"/article/(10\.\d{4,}/.+)", url)
        if m:
            doi = m.group(1)
            return f"https://link.springer.com/content/pdf/{doi}.pdf"
        # 3. Find PDF link in page
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/content/pdf/" in href.lower() or href.lower().endswith(".pdf"):
                return urljoin(url, href)
        return None
