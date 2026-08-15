# PaperHub — 一站式论文下载工具

整合多个学术论文平台，支持按名称、DOI、关键词搜索并下载论文。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 搜索论文
python main.py search "transformer attention"

# 指定平台搜索
python main.py search "attention is all you need" --platforms arxiv,crossref,openalex --limit 5

# 搜索中文论文
python main.py search "深度学习" --platforms cnki

# JSON 输出（AI 友好）
python main.py search "quantum computing" --all --limit 3 --json

# 按 DOI 下载
python main.py download 10.48550/arXiv.1706.03762

# 列出所有平台
python main.py platforms
```

## 支持平台 (11个)

| 平台 | 状态 | 说明 |
|:----|:----:|:-----|
| **arxiv** | ✅ | 预印本，物理/数学/CS |
| **crossref** | ✅ | DOI 元数据查询 |
| **openalex** | ✅ | 开放学术图谱 |
| **pubmed** | ✅ | 生物医学文献 |
| **semantic-scholar** | ✅ | AI 语义搜索 |
| **zenodo** | ✅ | CERN 开放存储库 |
| **core** | ✅ | 开放获取论文聚合 |
| **doaj** | ✅ | 开放获取期刊目录 |
| **sci-hub** | ✅ | 影子图书馆（DOI 下载） |
| **biorxiv** | ✅ | 生命科学预印本 |
| **cnki** | ✅ | 中文论文（百度学术+知网） |

## JSON 输出格式（AI 友好）

```json
[
  {
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani", "Noam Shazeer", ...],
    "doi": "10.48550/arXiv.1706.03762",
    "year": "2017",
    "source": "1706.03762",
    "url": "https://arxiv.org/abs/1706.03762",
    "pdf_url": "https://arxiv.org/pdf/1706.03762",
    "abstract": "...",
    "platform": "arxiv"
  }
]
```

## 下载目录

论文默认下载到 `~/paper-downloads/`，按平台分目录存放。

## 添加新平台

在 `platforms/` 目录下创建新文件，继承 `BasePlatform` 即可自动注册：

```python
from . import BasePlatform
from core.utils import PaperResult

class MyPlatform(BasePlatform):
    @property
    def name(self): return "my-platform"
    def search(self, query, limit=10, **kwargs): ...
    def fetch_by_doi(self, doi): ...
    def download(self, paper): ...
```