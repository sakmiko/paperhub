"""arXiv 论文平台"""
import re
import xml.etree.ElementTree as ET
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..')); from core.utils import PaperResult, download_pdf, fetch, safe_filename
from . import BasePlatform

# arXiv API 的 Atom 命名空间
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"

API_BASE = "http://export.arxiv.org/api/query"


def _parse_arxiv_id(entry_id: str) -> str:
    """从 entry id（如 http://arxiv.org/abs/1706.03762v1）中提取 arXiv ID（不含版本号）"""
    # 格式: http://arxiv.org/abs/XXXX.XXXXXvX 或 http://arxiv.org/abs/XXXX.XXXXX
    m = re.search(r"/abs/(\d+\.\d+)(?:v\d+)?$", entry_id)
    if m:
        return m.group(1)
    return entry_id.rsplit("/", 1)[-1]


def _parse_entry(entry: ET.Element) -> Optional[PaperResult]:
    """解析单个 Atom entry 元素为 PaperResult"""
    title_el = entry.find(f"{{{ATOM_NS}}}title")
    summary_el = entry.find(f"{{{ATOM_NS}}}summary")
    id_el = entry.find(f"{{{ATOM_NS}}}id")
    published_el = entry.find(f"{{{ATOM_NS}}}published")
    doi_el = entry.find(f"{{{ARXIV_NS}}}doi")

    if title_el is None or id_el is None:
        return None

    # 标题：去除多余空白
    title = " ".join(title_el.text.split()) if title_el.text else ""

    # 摘要
    abstract = " ".join(summary_el.text.split()) if summary_el is not None and summary_el.text else ""

    # arXiv ID
    entry_id = id_el.text.strip()
    arxiv_id = _parse_arxiv_id(entry_id)

    # 发布日期 → 年份
    year = ""
    if published_el is not None and published_el.text:
        year = published_el.text[:4]

    # 作者
    authors = []
    for author_el in entry.findall(f"{{{ATOM_NS}}}author"):
        name_el = author_el.find(f"{{{ATOM_NS}}}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    # DOI
    doi = ""
    if doi_el is not None and doi_el.text:
        doi = doi_el.text.strip()

    # 链接：找到 PDF 链接和页面链接
    pdf_url = ""
    url = ""
    for link_el in entry.findall(f"{{{ATOM_NS}}}link"):
        rel = link_el.get("rel", "")
        href = link_el.get("href", "")
        link_type = link_el.get("title", "")
        if rel == "related" and link_type == "pdf":
            pdf_url = href
        elif rel == "alternate":
            url = href

    # 如果没找到 PDF 链接，构建标准 PDF URL
    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # 如果没找到抽象页面链接
    if not url:
        url = f"https://arxiv.org/abs/{arxiv_id}"

    return PaperResult(
        title=title,
        authors=authors,
        doi=doi,
        year=year,
        source=arxiv_id,
        url=url,
        pdf_url=pdf_url,
        abstract=abstract,
        platform="arxiv",
    )


class ArxivPlatform(BasePlatform):
    """arXiv 论文平台"""

    @property
    def name(self) -> str:
        return "arxiv"

    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        """按关键词搜索 arXiv 论文

        支持的搜索前缀（传递给 search_query）：
            all:     全文搜索（默认）
            ti:      标题
            au:      作者
            abs:     摘要
            co:      合作者
            jr:      期刊参考
            cat:     分类
            rn:      报告编号

        示例：
            search("transformer")                     → 全文搜索
            search("ti:attention au:vaswani")         → 标题+作者
            search("cat:cs.CL")                       → 按分类
        """
        # 构建查询参数
        params = {
            "search_query": query,
            "start": kwargs.get("start", 0),
            "max_results": min(limit, 1000),
        }

        resp = fetch(API_BASE, params=params)
        if not resp or resp.status_code != 200:
            return []

        return self._parse_feed(resp.text)

    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        """按 DOI 或 arXiv ID 获取论文

        - 如果输入以 10. 开头，视为 DOI 并通过 search_query 查询
        - 如果输入是 arXiv ID（如 1706.03762 或 arXiv:1706.03762），通过 id_list 查询
        """
        doi = doi.strip()

        # 判断是否为 arXiv ID
        arxiv_match = re.match(r"^(?:arXiv:)?(\d{4}\.\d{4,5})(?:v\d+)?$", doi)

        if arxiv_match:
            # 通过 id_list 精确查询 arXiv ID
            params = {"id_list": arxiv_match.group(1), "max_results": 1}
        else:
            # 假设是 DOI，通过 search_query 查询
            # 清理 DOI 前缀
            clean_doi = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
            params = {"search_query": f"doi:{clean_doi}", "max_results": 1}

        resp = fetch(API_BASE, params=params)
        if not resp or resp.status_code != 200:
            return None

        results = self._parse_feed(resp.text)
        return results[0] if results else None

    def download(self, paper: PaperResult) -> Optional[str]:
        """下载 arXiv 论文 PDF"""
        if not paper.pdf_url:
            return None
        filename = safe_filename(f"{paper.source}_{paper.title}")
        path = download_pdf(paper.pdf_url, filename, subdir="arxiv")
        if path is not None:
            return str(path)
        return None

    def _parse_feed(self, xml_text: str) -> List[PaperResult]:
        """解析 Atom XML feed 返回 PaperResult 列表"""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        papers = []
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            paper = _parse_entry(entry)
            if paper is not None:
                papers.append(paper)
        return papers