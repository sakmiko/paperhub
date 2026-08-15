"""核心 __init__"""
from .config import DOWNLOAD_DIR, API_BASE
from .utils import PaperResult, fetch, post, download_pdf, safe_filename, extract_doi

__all__ = ["PaperResult", "fetch", "post", "download_pdf", "safe_filename",
           "extract_doi", "DOWNLOAD_DIR", "API_BASE"]