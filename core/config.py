"""论文下载器核心配置"""
import os
from pathlib import Path

# 下载目录
DOWNLOAD_DIR = Path(os.path.expanduser("~")) / "paper-downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)

# API 端点配置
API_BASE = {
    "arxiv": "http://export.arxiv.org/api/query",
    "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
    "crossref": "https://api.crossref.org/works",
    "openalex": "https://api.openalex.org/works",
    "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper",
    "core": "https://api.core.ac.uk/v3",
    "unpaywall": "https://api.unpaywall.org/v2",
    "doaj": "https://api.doaj.org/search/articles",
    "zenodo": "https://zenodo.org/api/records",
    "scidb": "https://annas-archive.org",
}

# 请求超时
TIMEOUT = 30

# 用户代理
USER_AGENT = "PaperDownloader/1.0 (Academic Research Tool; mailto:user@example.com)"