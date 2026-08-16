"""工具函数"""
import hashlib
import json
import re
import time
from pathlib import Path
from typing import List, Optional

import requests

from .config import DOWNLOAD_DIR, TIMEOUT, USER_AGENT


def safe_filename(text: str, max_len: int = 80) -> str:
    """将文本转为安全的文件名"""
    name = re.sub(r'[\\/:*?"<>|]', '_', text)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:max_len]


def fetch(url: str, headers: Optional[dict] = None, params: Optional[dict] = None,
           timeout: int = TIMEOUT, retries: int = 3) -> Optional[requests.Response]:
    """带重试的 HTTP GET 请求"""
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    for i in range(retries):
        try:
            resp = requests.get(url, headers=h, params=params, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(5)
                continue
            return resp
        except requests.RequestException:
            if i == retries - 1:
                return None
            time.sleep(2)
    return None


def post(url: str, json_data: dict, headers: Optional[dict] = None,
         timeout: int = TIMEOUT) -> Optional[requests.Response]:
    """带重试的 HTTP POST 请求"""
    h = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    try:
        return requests.post(url, json=json_data, headers=h, timeout=timeout)
    except requests.RequestException:
        return None


def download_pdf(url: str, filename: str, subdir: str = "") -> Optional[Path]:
    """下载 PDF 文件，验证有效性"""
    save_dir = DOWNLOAD_DIR / subdir
    save_dir.mkdir(exist_ok=True, parents=True)
    save_path = save_dir / f"{filename}.pdf"

    if save_path.exists() and save_path.stat().st_size > 1000:
        if save_path.open('rb').read(1024).startswith(b'%PDF'):
            return save_path
        save_path.unlink(missing_ok=True)

    resp = fetch(url, headers={"User-Agent": "Mozilla/5.0"})
    if not resp or resp.status_code != 200:
        return None

    content = resp.content
    if content[:100].strip().startswith(b'<') or b'<!DOCTYPE' in content[:500]:
        text = content.decode('utf-8', errors='ignore')
        pdf_urls = re.findall(r'(https?://[^\s"\'<>]+\.pdf[^\s"\'<>]*)', text)
        for pdf_url in pdf_urls[:3]:
            pdf_url = re.sub(r'[#?].*$', '', pdf_url)
            resp2 = fetch(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp2 and resp2.status_code == 200:
                content = resp2.content
                if content[:100].strip().startswith(b'%PDF'):
                    save_path.write_bytes(content)
                    return save_path
        return None

    if content[:100].strip().startswith(b'%PDF'):
        save_path.write_bytes(content)
        return save_path
    save_path.write_bytes(content)
    return save_path


def extract_doi(text: str) -> Optional[str]:
    """从文本中提取 DOI"""
    m = re.search(r'10\.\d{4,}/[^\s]+', text)
    return m.group(0) if m else None


def _title_similarity(t1: str, t2: str) -> float:
    """计算两个标题的相似度（基于字符交集）"""
    if not t1 or not t2:
        return 0.0
    s1, s2 = t1.lower().strip(), t2.lower().strip()
    if s1 == s2:
        return 1.0
    # 去空格后计算字符级相似度
    chars1 = set(s1.replace(' ', ''))
    chars2 = set(s2.replace(' ', ''))
    common = len(chars1 & chars2)
    total = max(len(chars1), len(chars2))
    return common / total if total > 0 else 0.0


def dedup_results(results: List['PaperResult']) -> List['PaperResult']:
    """去重：DOI 优先，其次标题相似度"""
    by_doi = {}
    for r in results:
        if r.doi:
            doi = r.doi.lower().strip()
            if doi in by_doi:
                old = by_doi[doi]
                # 保留字段更丰富的
                old_score = len([v for v in [old.title, old.doi, old.abstract, old.pdf_url] if v]) + len(old.authors)
                new_score = len([v for v in [r.title, r.doi, r.abstract, r.pdf_url] if v]) + len(r.authors)
                if new_score > old_score:
                    by_doi[doi] = r
            else:
                by_doi[doi] = r

    doi_deduped = list(by_doi.values())
    # 按标题相似度二次去重
    final = []
    for r in doi_deduped:
        is_dup = False
        for existing in final:
            if _title_similarity(r.title, existing.title) > 0.8:
                is_dup = True
                break
        if not is_dup:
            final.append(r)
    return final


def sort_results(results: List['PaperResult'], by: str = "relevance", reverse: bool = True) -> List['PaperResult']:
    """排序：按年份、标题或相关性"""
    if by == "year":
        def key_fn(r):
            try:
                return int(r.year) if r.year else 0
            except ValueError:
                return 0
    elif by == "title":
        key_fn = lambda r: (r.title or "").lower()
        reverse = False
    else:
        def key_fn(r):
            score = 0
            if r.doi:
                score += 1
            if r.pdf_url:
                score += 2
            if r.abstract:
                score += 1
            if r.authors:
                score += 1
            return score
    return sorted(results, key=key_fn, reverse=reverse)


def filter_results(results: List['PaperResult'], year_from: str = None,
                    year_to: str = None, author: str = None,
                    journal: str = None) -> List['PaperResult']:
    """过滤结果"""
    filtered = results
    if year_from:
        filtered = [r for r in filtered if r.year and r.year.isdigit() and int(r.year) >= int(year_from)]
    if year_to:
        filtered = [r for r in filtered if r.year and r.year.isdigit() and int(r.year) <= int(year_to)]
    if author:
        author_lower = author.lower()
        filtered = [r for r in filtered if any(author_lower in a.lower() for a in r.authors)]
    if journal:
        journal_lower = journal.lower()
        filtered = [r for r in filtered if journal_lower in r.source.lower()]
    return filtered


def export_bibtex(results: List['PaperResult']) -> str:
    """导出 BibTeX 格式"""
    entries = []
    for i, r in enumerate(results):
        if not r.title:
            continue
        key = re.sub(r'[^a-zA-Z0-9]', '', (r.authors[0] if r.authors else "Unknown").split()[-1].lower() if r.authors else "unknown")
        key += r.year if r.year else "0000"
        key += str(i)
        authors = " and ".join(r.authors[:5]) if r.authors else "Unknown"
        entry = f"@article{{{key},\n"
        entry += f"  title = {{{r.title}}},\n"
        entry += f"  author = {{{authors}}},\n"
        if r.year:
            entry += f"  year = {{{r.year}}},\n"
        if r.doi:
            entry += f"  doi = {{{r.doi}}},\n"
        if r.source:
            entry += f"  journal = {{{r.source}}},\n"
        if r.url:
            entry += f"  url = {{{r.url}}},\n"
        entry += "}"
        entries.append(entry)
    return "\n\n".join(entries)


def export_csv(results: List['PaperResult']) -> str:
    """导出 CSV 格式"""
    import io
    output = io.StringIO()
    output.write("title,authors,doi,year,journal,url,platform\n")
    for r in results:
        title = r.title.replace('"', '""') if r.title else ""
        authors = "; ".join(r.authors[:5]).replace('"', '""') if r.authors else ""
        output.write(f'"{title}","{authors}","{r.doi}","{r.year}","{r.source}","{r.url}","{r.platform}"\n')
    return output.getvalue()


def format_results(results: List['PaperResult'], fmt: str = "text") -> str:
    """格式化输出"""
    if fmt == "json":
        return json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2)
    elif fmt == "bibtex":
        return export_bibtex(results)
    elif fmt == "csv":
        return export_csv(results)

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"  [{i}] {r.title}")
        if r.authors:
            lines.append(f"      👤 {', '.join(r.authors[:3])}")
        if r.doi:
            lines.append(f"      🔗 DOI: {r.doi}")
        if r.year:
            lines.append(f"      📅 {r.year}")
        if r.source:
            lines.append(f"      📰 {r.source[:50]}")
        if r.platform:
            lines.append(f"      🏷️ {r.platform}")
        lines.append("")
    return "\n".join(lines)


class PaperResult:
    """统一的论文结果模型"""
    def __init__(self, title: str = "", authors: list = None, doi: str = "",
                 year: str = "", source: str = "", url: str = "",
                 pdf_url: str = "", abstract: str = "", platform: str = ""):
        self.title = title
        self.authors = authors or []
        self.doi = doi
        self.year = year
        self.source = source
        self.url = url
        self.pdf_url = pdf_url
        self.abstract = abstract
        self.platform = platform

    def __repr__(self):
        return f"[{self.platform}] {self.title} ({self.year})"

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v}