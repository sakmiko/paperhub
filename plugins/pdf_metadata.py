"""PDF 元数据提取插件 — 用 PyMuPDF 提取 PDF 内嵌的标题/作者/DOI"""
import os
import re
from pathlib import Path
from typing import Optional

from plugins import Plugin, register


class PdfMetadataPlugin(Plugin):
    name = "pdf_metadata"
    description = "PDF 元数据提取：自动修正下载文件的命名和元数据"
    requires = ["fitz"]  # PyMuPDF

    def setup(self, config: dict) -> None:
        super().setup(config)
        self._rename_files = config.get("rename_files", True)

    def on_download(self, paper, path: str) -> str:
        """下载后提取 PDF 元数据，修正文件名"""
        if not path or not os.path.exists(path):
            return path

        try:
            import fitz
            doc = fitz.open(path)
            meta = doc.metadata or {}

            # 提取元数据
            pdf_title = meta.get("title", "")
            pdf_author = meta.get("author", "")

            # 从 PDF 内容提取 DOI
            doi = ""
            if not paper.doi:
                text = doc[0].get_text()[:2000] if doc.page_count > 0 else ""
                m = re.search(r'10\.\d{4,}/[^\s"\'<>]+', text)
                if m:
                    doi = m.group(0)
                    paper.doi = doi

            # 用 PDF 标题修正 PaperResult
            if pdf_title and len(pdf_title) > 5 and not paper.title:
                paper.title = pdf_title
            if pdf_author and not paper.authors:
                paper.authors = [a.strip() for a in pdf_author.split(";") if a.strip()][:5]

            doc.close()

            # 重命名文件
            if self._rename_files and paper.title:
                from core.utils import safe_filename
                new_name = safe_filename(paper.title) + ".pdf"
                new_path = str(Path(path).parent / new_name)
                if new_path != path and not os.path.exists(new_path):
                    os.rename(path, new_path)
                    return new_path

        except Exception:
            pass

        return path


register(PdfMetadataPlugin())
