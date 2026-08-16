"""核心 __init__"""
from .config import DOWNLOAD_DIR, API_BASE
from .utils import PaperResult, fetch, post, download_pdf, safe_filename, extract_doi

__version__ = "0.1.0"

__all__ = ["PaperResult", "fetch", "post", "download_pdf", "safe_filename",
           "extract_doi", "DOWNLOAD_DIR", "API_BASE", "__version__"]