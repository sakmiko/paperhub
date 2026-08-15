<p align="center">
  <img src="https://img.shields.io/badge/PaperHub-v1.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/platforms-12-green" alt="Platforms">
  <img src="https://img.shields.io/badge/transport-journals-73-orange" alt="Transport Journals">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
</p>

# 📚 PaperHub — 一站式学术论文搜索与下载工具

> 整合 12+ 学术论文平台，支持交通领域 73 本期刊模糊搜索，一键搜索、下载、导出。

## ✨ 特性

### 🔍 多平台搜索
| 平台 | 类型 | 覆盖领域 |
|:----|:-----|:---------|
| **arXiv** | 预印本 | 物理、数学、CS、定量生物学 |
| **PubMed Central** | 开放获取 | 生物医学 (11.6M+ 全文) |
| **Crossref** | DOI 元数据 | 全学科 |
| **OpenAlex** | 开放学术图谱 | 全学科 (免费 API) |
| **Semantic Scholar** | AI 语义搜索 | 计算机科学、生物医学 |
| **CORE** | OA 聚合 | 全学科 (2.5 亿+ OA) |
| **DOAJ** | OA 期刊目录 | 2 万+ OA 期刊 |
| **Zenodo** | CERN 存储库 | 全学科 |
| **bioRxiv/medRxiv** | 预印本 | 生命科学、医学 |
| **Sci-Hub** | 影子图书馆 | 全学科 (8800 万+) |
| **CNKI/iData** | 中文 | 知网镜像站 |
| **Bohrium (玻尔)** | AI 科研平台 | 1.6 亿+ 论文 (需 API Key) |

### 🚌 交通领域增强
- 73 本交通期刊模糊搜索
- TRB 系列 (TRR, TR-A~F)
- Transportation Science (INFORMS)
- IEEE T-ITS, J. Transport Geography
- 13 本中文交通期刊
- 模糊匹配：`trr` → Transportation Research Record

### 📥 智能下载
- 优先 OA 直链，Sci-Hub 兜底
- PDF 自动校验（无效自动重试）
- 三种模式：单 DOI / 搜索+下载 / 批量文件

### 📊 结果处理
- 自动去重（DOI + 标题相似度）
- 排序（年份 / 标题 / 相关性）
- 过滤（年份范围 / 作者 / 期刊）
- 导出（JSON / BibTeX / CSV）

## 🚀 快速开始

```bash
# 1. 安装
git clone https://github.com/sakmiko/paperhub.git
cd paperhub
pip install -r requirements.txt

# 2. 搜索
python main.py search "attention is all you need"

# 3. 交通领域搜索
python main.py search "bus rapid transit" --transport --limit 5

# 4. 按期刊过滤（模糊匹配）
python main.py search "modular bus" --journal "trr" --limit 3

# 5. 下载
python main.py download 10.48550/arXiv.1706.03762

# 6. 搜索+下载
python main.py download --search "transformer" --limit 3

# 7. 导出
python main.py search "deep learning" --platforms arxiv,crossref --limit 10 --export bibtex
```

## 📖 使用指南

### 搜索命令

```bash
# 基本搜索
python main.py search "query"                          # 全部平台
python main.py search "query" --platforms arxiv,crossref # 指定平台
python main.py search "query" --all --limit 5           # 所有平台，5条/平台

# 交通领域搜索
python main.py search "bus transit" --transport         # 跨16本核心期刊
python main.py search "bus transit" --journal "trr"     # 指定期刊（模糊匹配）
python main.py search "公交调度" --journal "交通运输"     # 中文期刊
python main.py journals                                  # 列出所有交通期刊

# 高级过滤
python main.py search "transit" --transport --year-from 2020 --year-to 2024
python main.py search "transit" --transport --author "Hensher"
python main.py search "transit" --transport --sort year

# 导出
python main.py search "query" --export bibtex           # BibTeX
python main.py search "query" --export csv              # CSV
python main.py search "query" --json                    # JSON
```

### 下载命令

```bash
# 单篇下载
python main.py download 10.48550/arXiv.1706.03762       # DOI
python main.py download 1706.03762                       # arXiv ID

# 搜索+下载
python main.py download --search "attention is all you need" --limit 3

# 批量下载
echo "10.48550/arXiv.1706.03762" > doids.txt
echo "10.48550/arXiv.2105.02723" >> doids.txt
python main.py download --from-file doids.txt
```

## 🏗️ 项目结构

```
paperhub/
├── main.py                 # CLI 入口
├── core/
│   ├── config.py           # 配置（API 端点、下载目录）
│   └── utils.py            # 工具函数（搜索、下载、去重、导出、格式化）
├── platforms/              # 12 个论文平台（自动发现）
│   ├── arxiv.py
│   ├── pubmed.py
│   ├── crossref.py
│   ├── openalex.py
│   ├── semanticscholar.py
│   ├── core.py
│   ├── doaj.py
│   ├── zenodo.py
│   ├── biorxiv.py
│   ├── scidb.py (Sci-Hub)
│   ├── cnki.py (知网)
│   └── bohrium.py (玻尔)
├── domain/
│   ├── __init__.py
│   └── transport.py        # 交通领域：73 本期刊 + 模糊搜索
├── config.yaml             # 用户配置模板
├── pyproject.toml           # 现代 Python 项目配置
├── setup.py                 # 传统安装配置
└── requirements.txt         # 依赖（仅 requests）
```

## 🔧 配置

### API Keys（可选）
部分平台需要 API Key 才能完整使用：

```bash
# CORE API（免费注册: https://core.ac.uk/services/api）
export CORE_API_KEY=your_key

# Bohrium 玻尔 API
export BOHRIUM_API_KEY=your_key
```

或编辑 `config.yaml`：
```yaml
keys:
  core_api: "your_key"
  bohrium_api: "your_key"
```

### 下载目录
默认下载到 `~/paper-downloads/`，按平台分目录存放。
可通过 `config.yaml` 修改：
```yaml
downloads:
  directory: ~/paper-downloads
  timeout: 30
  retries: 3
```

## 📊 平台实测状态

| 平台 | 搜索 | 下载 | 说明 |
|:----|:----:|:----:|:-----|
| ✅ arXiv | 0.2s | PDF 直链 | 最稳定 |
| ✅ PubMed | 0.5s | PMC 全文 | 生物医学 |
| ✅ Crossref | 0.3s | — | 元数据查询 |
| ✅ OpenAlex | 0.7s | OA 链接 | 免费，速度快 |
| ✅ Semantic Scholar | 0.6s | OA PDF | 有 429 限流 |
| ✅ DOAJ | 0.2s | OA PDF | OA 期刊 |
| ✅ Zenodo | 1.0s | PDF 直链 | CERN 存储 |
| ⚠️ CORE | — | — | 需 API Key |
| ⚠️ sci-hub | — | 7 镜像轮换 | 影子库 |
| ⚠️ CNKI | — | — | 中文网站 |
| ⚠️ Bohrium | — | — | 需 API Key |

## 🤝 贡献指南

添加新平台只需两步：

1. 在 `platforms/` 下创建新文件，继承 `BasePlatform`：

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

2. 自动注册！无需修改任何配置。

## 📄 许可

MIT License

## 🙏 致谢

- [arXiv](https://arxiv.org/)
- [PubMed Central](https://www.ncbi.nlm.nih.gov/pmc/)
- [Crossref](https://www.crossref.org/)
- [OpenAlex](https://openalex.org/)
- [Semantic Scholar](https://www.semanticscholar.org/)
- [CORE](https://core.ac.uk/)
- [DOAJ](https://doaj.org/)
- [Zenodo](https://zenodo.org/)
- [bioRxiv](https://www.biorxiv.org/)
- [Sci-Hub](https://sci-hub.se/)
- [Bohrium (玻尔)](https://www.bohrium.com/)