"""通用HTML页面PDF链接发现适配器（fallback）"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from platforms.publisher_adapters import BaseAdapter


class GenericAdapter(BaseAdapter):
    def can_handle(self, url: str) -> bool:
        return True  # 通用适配器始终可用

    def extract_pdf_url(self, html: str, url: str = ""):
        soup = BeautifulSoup(html, "html.parser")
        # 1. citation_pdf_url meta tag（最可靠）
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            return urljoin(url, meta["content"])
        # 2. 扫描所有链接，找包含PDF标记的
        pdf_markers = (".pdf", "/pdf", "/epdf", "/pdfft", "download=true")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            low = href.lower()
            if any(m in low for m in pdf_markers):
                return urljoin(url, href)
        # 3. 扫描 <link> 和 <iframe> 等
        for tag in soup.find_all(["link", "iframe", "embed"], src=True):
            src = tag.get("src", "")
            if src and any(m in src.lower() for m in pdf_markers):
                return urljoin(url, src)
        # 4. 正则搜索HTML中的PDF URL
        for m in re.finditer(r'(https?://[^\s"\'<>]+\.pdf[^\s"\'<>]*)', html):
            return m.group(1)
        return None
