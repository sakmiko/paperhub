"""CNKI 中文论文平台（通过 iData 镜像站）"""
import re
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, fetch, safe_filename, download_pdf
from . import BasePlatform


class CNKIPlatform(BasePlatform):
    """知网论文下载（通过 iData 镜像站 + 百度学术搜索）

    iData: https://www.cn-ki.net/ 是全球最大的知网镜像站
    百度学术: https://xueshu.baidu.com/ 提供来源检测
    """

    @property
    def name(self) -> str:
        return "cnki"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        results = []
        # 方式1: 通过百度学术搜索中文论文
        results.extend(self._search_baidu(query, limit))
        return results

    def _search_baidu(self, query: str, limit: int) -> List[PaperResult]:
        """通过百度学术搜索"""
        results = []
        try:
            url = "https://xueshu.baidu.com/s"
            params = {"wd": query, "rsv_bp": 0, "tn": "SE_baiduxueshu_c1g0"}
            resp = fetch(url, params=params, timeout=15)
            if not resp:
                return []

            html = resp.text
            # 解析百度学术搜索结果
            # 查找论文标题和链接
            title_pattern = re.compile(r'<a[^>]+href="(https?://xueshu\.baidu\.com/usercenter/paper/show[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            matches = title_pattern.findall(html)

            for href, title_text in matches[:limit]:
                title = re.sub(r'<[^>]+>', '', title_text).strip()
                if not title:
                    continue
                # 抓取详情页获取更多信息
                detail = self._fetch_baidu_detail(href)
                if detail:
                    results.append(detail)
                else:
                    results.append(PaperResult(
                        title=title,
                        url=href,
                        platform=self.name,
                    ))
        except Exception:
            pass
        return results

    def _fetch_baidu_detail(self, url: str) -> Optional[PaperResult]:
        """获取百度学术详情页的详细信息"""
        try:
            resp = fetch(url, timeout=10)
            if not resp:
                return None
            html = resp.text

            # 提取标题
            title_match = re.search(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""

            # 提取作者
            authors = []
            author_matches = re.findall(r'<a[^>]+class="author_name"[^>]*>(.*?)</a>', html)
            for a in author_matches:
                authors.append(re.sub(r'<[^>]+>', '', a).strip())

            # 提取摘要
            abstract_match = re.search(r'<div[^>]+class="abstract"[^>]*>(.*?)</div>', html, re.DOTALL)
            abstract = re.sub(r'<[^>]+>', '', abstract_match.group(1)).strip() if abstract_match else ""

            # 提取 DOI
            doi_match = re.search(r'DOI[：:]\s*(10\.\d{4,}/[^\s<]+)', html)
            doi = doi_match.group(1) if doi_match else ""

            # 提取年份
            year_match = re.search(r'(\d{4})[年\s]', html)
            year = year_match.group(1) if year_match else ""

            # 提取来源（期刊名）
            source_match = re.search(r'来源[：:]\s*([^<]+)', html)
            source = source_match.group(1).strip() if source_match else ""

            return PaperResult(
                title=title,
                authors=authors[:5],
                doi=doi,
                year=year,
                source=source,
                url=url,
                abstract=abstract[:500],
                platform=self.name,
            )
        except Exception:
            return None

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        # 通过百度学术搜索 DOI
        results = self.search(doi, limit=1)
        return results[0] if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        """尝试通过 iData 下载"""
        if not paper.title:
            return None
        try:
            # iData 搜索
            url = "https://www.cn-ki.net/search"
            params = {"q": paper.title}
            resp = fetch(url, params=params, timeout=15)
            if not resp:
                return None
            # 查找下载链接
            html = resp.text
            download_links = re.findall(r'(https?://www\.cn-ki\.net/paper/[^"\']+)', html)
            if download_links:
                dl_url = download_links[0]
                path = download_pdf(dl_url, safe_filename(paper.title), "cnki")
                if path:
                    return str(path)
        except Exception:
            pass
        return None