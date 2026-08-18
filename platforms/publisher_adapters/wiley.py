"""Wiley Online Library PDF链接提取适配器"""
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from platforms.publisher_adapters import BaseAdapter


class WileyAdapter(BaseAdapter):
    def can_handle(self, url: str) -> bool:
        return "wiley.com" in url.lower()

    def extract_pdf_url(self, html: str, url: str = ""):
        soup = BeautifulSoup(html, "html.parser")
        # 1. citation_pdf_url meta tag
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])
        # 2. Wiley DOI-based PDF: /doi/pdf/10.1007/xxx or /doi/epdf/...
        for a in soup.find_all("a", href=True):
            href = a["href"]
            low = href.lower()
            if "/doi/pdf/" in low or "/doi/epdf/" in low or "/doi/pdfdirect/" in low:
                return urljoin(url, href)
        # 3. Direct .pdf link
        for a in soup.find_all("a", href=True):
            if a["href"].lower().endswith(".pdf"):
                return urljoin(url, a["href"])
        return None
