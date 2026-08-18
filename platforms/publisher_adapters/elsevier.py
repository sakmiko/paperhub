"""Elsevier/ScienceDirect PDF链接提取适配器"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from platforms.publisher_adapters import BaseAdapter


class ElsevierAdapter(BaseAdapter):
    def can_handle(self, url: str) -> bool:
        u = url.lower()
        return "sciencedirect.com" in u or "elsevier.com" in u

    def extract_pdf_url(self, html: str, url: str = ""):
        soup = BeautifulSoup(html, "html.parser")
        # 1. citation_pdf_url meta tag
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])
        # 2. PII-based PDF URL: /science/article/pii/XXXX/pdfft
        m = re.search(r"/pii/([A-Z0-9]+)", url, re.I)
        if m:
            return f"https://www.sciencedirect.com/science/article/pii/{m.group(1)}/pdfft"
        # 3. Look for PDF links in the page
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "pdfft" in href.lower() or href.lower().endswith(".pdf"):
                return urljoin(url, href)
        return None
