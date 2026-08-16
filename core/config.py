"""论文下载器核心配置"""
import os
from pathlib import Path

# 下载目录
DOWNLOAD_DIR = Path(os.path.expanduser("~")) / "paper-downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)

# 尝试从 config.yaml 加载配置
_config = {}
_config_path = Path(__file__).resolve().parent.parent / "config.yaml"
if _config_path.exists():
    try:
        import yaml
        with open(_config_path, encoding="utf-8") as f:
            _config = yaml.safe_load(f) or {}
        # 应用配置
        dl_cfg = _config.get("downloads", {})
        if dl_cfg.get("directory"):
            DOWNLOAD_DIR = Path(os.path.expanduser(dl_cfg["directory"]))
            DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)
    except ImportError:
        pass  # PyYAML 未安装，使用默认配置
    except Exception:
        pass

# API 端点配置
API_BASE = {
    "arxiv": "https://export.arxiv.org/api/query",
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
TIMEOUT = _config.get("downloads", {}).get("timeout", 30) if isinstance(_config.get("downloads"), dict) else 30

# 用户代理
USER_AGENT = "PaperHub/1.0 (Academic Research Tool; mailto:user@example.com)"