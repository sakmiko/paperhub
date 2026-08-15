"""Sci-Hub 下载平台"""
import re
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, download_pdf, safe_filename
from . import BasePlatform


class SciHubPlatform(BasePlatform):
    """Sci-Hub：通过 DOI 下载论文 PDF（仅下载，不搜索）"""

    MIRRORS = [
        "https://sci-hub.se",
        "https://sci-hub.ru",
        "https://sci-hub.st",
        "https://sci-hub.su",
        "https://sci-hub.box",
        "https://sci-hub.red",
        "https://sci-hub.mk",
    ]

    @property
    def name(self) -> str:
        return "sci-hub"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        return []

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        return PaperResult(
            title=f"Paper DOI: {doi}",
            doi=doi,
            url=f"https://doi.org/{doi}",
            platform=self.name,
        )

    def _extract_pdf_from_html(self, html: str, mirror: str) -> List[str]:
        """从 Sci-Hub HTML 页面中提取 PDF 下载链接"""
        candidates = []
        # 1. 直接查找 PDF URL
        pdf_urls = re.findall(r'(https?://[^\s"\'<>]+\.pdf[^\s"\'<>]*)', html)
        for u in pdf_urls:
            # 清理尾部
            u = re.sub(r'[#?].*$', '', u)
            if u not in candidates:
                candidates.append(u)
        # 2. 查找 embed/iframe 中的 src
        embeds = re.findall(r'<(?:embed|iframe)[^>]+src="([^"]+)"', html)
        for u in embeds:
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/"):
                u = mirror + u
            if u not in candidates:
                candidates.append(u)
        # 3. 查找 #pdf-embed 中的 data-src
        data_src = re.findall(r'data-src="([^"]+)"', html)
        for u in data_src:
            if u.startswith("//"):
                u = "https:" + u
            if u not in candidates:
                candidates.append(u)
        return candidates

    def download(self, paper: PaperResult) -> Optional[str]:
        if not paper.doi:
            return None
        filename = safe_filename(paper.title or paper.doi)

        for mirror in self.MIRRORS:
            url = f"{mirror}/{paper.doi}"
            # 先尝试直接作为 PDF 下载
            path = download_pdf(url, filename, "sci-hub")
            if path:
                # 检查是否为有效的 PDF
                content = open(path, 'rb').read(1024)
                if content.startswith(b'%PDF'):
                    return str(path)
                path.unlink()  # 删除无效文件

            # 获取 HTML 页面提取 PDF 链接
            resp = fetch(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
            if not resp:
                continue

            html = resp.text
            candidates = self._extract_pdf_from_html(html, mirror)

            for pdf_url in candidates[:5]:
                # 确保 URL 完整
                if pdf_url.startswith("//"):
                    pdf_url = "https:" + pdf_url
                elif pdf_url.startswith("/"):
                    pdf_url = mirror + pdf_url
                elif not pdf_url.startswith("http"):
                    continue

                path = download_pdf(pdf_url, filename, "sci-hub")
                if path:
                    content = open(path, 'rb').read(1024)
                    if content.startswith(b'%PDF'):
                        return str(path)
                    path.unlink()

        return None