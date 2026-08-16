#!/usr/bin/env python3
"""
PaperHub - 一站式学术论文搜索与下载工具

整合 12+ 学术平台，支持按名称、DOI、关键词搜索并下载论文。
交通领域增强：支持 TRB、TRR、Transportation Science 等 73 本交通期刊模糊搜索。

Usage:
  paperhub search "attention is all you need"
  paperhub search "transformer" --platforms arxiv,crossref --limit 10
  paperhub search "bus rapid transit" --transport --limit 5
  paperhub search "deep learning" --journal "trr" --limit 3 --export bibtex
  paperhub download 10.48550/arXiv.1706.03762
  paperhub download --search "transformer" --limit 3
  paperhub download --from-file doids.txt
  paperhub platforms
  paperhub journals
"""
import argparse
import importlib
import inspect
import json
import os
import pkgutil
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.utils import (
    PaperResult,
    download_pdf,
    safe_filename,
    dedup_results,
    sort_results,
    filter_results,
    format_results,
    export_bibtex,
    export_csv,
)
from platforms import BasePlatform

# ===== 下载优先级 =====
DOWNLOAD_PRIORITY = [
    "arxiv", "pubmed", "openalex", "semantic-scholar", "core",
    "doaj", "zenodo", "biorxiv", "bohrium",
    "crossref", "sci-hub", "cnki", "google-scholar", "ssrn",
]


# ===== 平台发现 =====
def discover_platforms() -> dict:
    found = {}
    import platforms as pkg
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname == "__init__" or ispkg:
            continue
        try:
            module = importlib.import_module(f"platforms.{modname}")
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BasePlatform) and obj is not BasePlatform:
                    try:
                        instance = obj()
                        found[instance.name] = instance
                    except Exception:
                        pass
        except Exception:
            pass
    return found


def get_platforms(platform_names: List[str] = None, all_platforms: bool = False) -> dict:
    available = discover_platforms()
    if all_platforms:
        return available
    if platform_names:
        names = [n.strip() for n in ",".join(platform_names).split(",")]
        return {n: available[n] for n in names if n in available}
    return available


def normalize_doi(doi: str) -> str:
    doi = doi.strip()
    doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi)
    doi = re.sub(r'^arxiv:', '', doi, flags=re.I)
    if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', doi):
        return doi
    doi = re.sub(r'(v\d+)$', '', doi)
    return doi


def is_valid_pdf(path: Path) -> bool:
    if not path or not path.exists():
        return False
    try:
        return path.open('rb').read(1024).startswith(b'%PDF')
    except Exception:
        return False


def try_download_single(platform, paper: PaperResult, filename: str) -> Optional[str]:
    try:
        path = platform.download(paper)
        if path:
            p = Path(path)
            if is_valid_pdf(p):
                return str(p)
            p.unlink(missing_ok=True)
    except Exception:
        pass
    return None


def try_download_parallel(platforms: dict, paper: PaperResult, priority: List[str] = None,
                           timeout: int = 30) -> Optional[str]:
    if priority is None:
        priority = DOWNLOAD_PRIORITY
    filename = safe_filename(paper.title or paper.doi or "paper")
    for name in priority:
        if name not in platforms:
            continue
        result = try_download_single(platforms[name], paper, filename)
        if result:
            return result
    return None


def try_download_arxiv_id(doi: str, platforms: dict) -> Optional[PaperResult]:
    m = re.match(r'10\.48550/arXiv\.(\d{4}\.\d{4,5})', doi)
    if not m:
        m = re.match(r'(\d{4}\.\d{4,5})', doi)
    if m and 'arxiv' in platforms:
        try:
            return platforms['arxiv'].fetch_by_doi(m.group(1))
        except Exception:
            pass
    return None


# ===== 搜索命令 =====
def cmd_search(args):
    # 交通领域搜索
    if args.transport or args.journal:
        try:
            from domain import search_transport, fuzzy_match_journal, TRANSPORT_JOURNALS
        except ImportError:
            print("❌ 交通领域模块未加载")
            sys.exit(1)

        if args.journal:
            matched = fuzzy_match_journal(args.journal)
            if not matched:
                print(f"❌ 未匹配到期刊: {args.journal}")
                print("可用: paperhub journals")
                return
            if not args.json:
                print(f"📚 匹配期刊: {', '.join(matched[:5])}")

        results = search_transport(args.query, journal=args.journal, limit=args.limit)
        if not results:
            print("❌ 未找到相关论文")
            return

        # 转为 PaperResult 对象
        paper_results = []
        for r in results:
            paper_results.append(PaperResult(
                title=r.get("title", ""),
                authors=r.get("authors", []),
                doi=r.get("doi", ""),
                year=r.get("year", ""),
                source=r.get("journal", ""),
                url=r.get("url", ""),
                platform=r.get("platform", "crossref"),
            ))

        # 去重和排序
        paper_results = dedup_results(paper_results)
        if args.sort:
            paper_results = sort_results(paper_results, by=args.sort)
        if args.year_from or args.year_to or args.author:
            paper_results = filter_results(paper_results, args.year_from, args.year_to, args.author)

        if args.json:
            print(json.dumps([r.to_dict() for r in paper_results], ensure_ascii=False, indent=2))
        elif args.export == "bibtex":
            print(export_bibtex(paper_results))
        elif args.export == "csv":
            print(export_csv(paper_results))
        else:
            print(f"\n📚 交通领域搜索: {args.query}")
            print(f"   共 {len(paper_results)} 篇:\n")
            print(format_results(paper_results, "text"))
        return

    # 普通搜索
    platforms = get_platforms(args.platforms, args.all)
    if not platforms:
        print("❌ 没有可用的平台")
        sys.exit(1)

    all_results = []
    for name, platform in platforms.items():
        try:
            results = platform.search(args.query, limit=args.limit)
            if results:
                all_results.extend(results)
                if not args.json and args.export != "bibtex" and args.export != "csv":
                    print(f"  ✅ [{name}] 找到 {len(results)} 篇")
        except Exception as e:
            if not args.json:
                print(f"  ⚠️ [{name}] 失败: {e}")
        time.sleep(0.2)

    # 去重排序过滤
    all_results = dedup_results(all_results)
    if args.sort:
        all_results = sort_results(all_results, by=args.sort)
    if args.year_from or args.year_to or args.author:
        all_results = filter_results(all_results, args.year_from, args.year_to, args.author)

    if args.json:
        print(json.dumps([r.to_dict() for r in all_results], ensure_ascii=False, indent=2))
    elif args.export == "bibtex":
        print(export_bibtex(all_results))
    elif args.export == "csv":
        print(export_csv(all_results))
    else:
        print(f"\n{'='*50}")
        print(f"共 {len(all_results)} 篇结果")
        print(format_results(all_results, "text"))


# ===== 下载命令 =====
def cmd_download(args):
    platforms = get_platforms(all_platforms=True)
    if not platforms:
        print("❌ 没有可用的平台")
        sys.exit(1)

    # 搜索+下载模式
    if args.search:
        print(f"🔍 搜索: {args.search}")
        results = []
        for name in ["arxiv", "crossref", "openalex", "semantic-scholar"]:
            if name in platforms:
                try:
                    r = platforms[name].search(args.search, limit=args.limit or 5)
                    results.extend(r)
                except Exception:
                    pass
                time.sleep(0.3)
        results = dedup_results(results)
        if not results:
            print("❌ 未搜索到相关论文")
            return
        print(f"📚 找到 {len(results)} 篇，开始下载...")
        success = 0
        for i, paper in enumerate(results[: (args.limit or 5)]):
            print(f"\n[{i+1}/{min(len(results), args.limit or 5)}] {paper.title[:60]}")
            path = try_download_parallel(platforms, paper)
            if path:
                print(f"    ✅ 成功: {path}")
                success += 1
            else:
                print(f"    ❌ 失败")
        print(f"\n✅ 下载完成: {success}/{min(len(results), args.limit or 5)} 篇成功")
        return

    # 从文件下载
    if args.from_file:
        try:
            doids = [l.strip() for l in open(args.from_file).readlines() if l.strip()]
        except FileNotFoundError:
            print(f"❌ 文件不存在: {args.from_file}")
            sys.exit(1)
        print(f"📋 从文件读取 {len(doids)} 个 DOI")
        success = 0
        for i, doi_str in enumerate(doids):
            doi = normalize_doi(doi_str)
            print(f"\n[{i+1}/{len(doids)}] {doi}")
            paper = PaperResult(doi=doi, title=f"Paper_{doi.replace('/', '_')}")
            for name in DOWNLOAD_PRIORITY:
                if name not in platforms:
                    continue
                try:
                    info = platforms[name].fetch_by_doi(doi)
                    info_doi = normalize_doi(info.doi) if info and info.doi else ""
                    if info and info.title and "Paper DOI" not in info.title and (info_doi == doi or doi in info_doi):
                        paper = info
                        if not args.json:
                            print(f"  ✅ [{name}] {info.title[:60]}")
                        break
                except Exception:
                    pass
            path = try_download_parallel(platforms, paper)
            if path:
                print(f"    ✅ 成功: {path}")
                success += 1
            else:
                print(f"    ❌ 失败")
        print(f"\n✅ 完成: {success}/{len(doids)}")
        return

    # 单 DOI 下载
    doi = normalize_doi(args.doi)
    print(f"🔍 尝试下载: {doi}")
    paper = PaperResult(doi=doi, title=f"Paper_{doi.replace('/', '_')}")

    for name in DOWNLOAD_PRIORITY:
        if name not in platforms:
            continue
        try:
            info = platforms[name].fetch_by_doi(doi)
            if info and info.title and "Paper DOI" not in info.title:
                info_doi = normalize_doi(info.doi) if info.doi else ""
                if info_doi == doi or info_doi in doi or doi in info_doi:
                    paper = info
                    if not args.json:
                        print(f"  ✅ [{name}] {info.title[:60]}")
                    break
        except Exception:
            pass

    arxiv_result = try_download_arxiv_id(doi, platforms)
    if arxiv_result:
        paper = arxiv_result

    path = try_download_parallel(platforms, paper)

    if args.json:
        result = {"doi": doi, "title": paper.title, "success": path is not None, "path": path or ""}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif path:
        print(f"\n✅ 下载成功: {path}")
    else:
        print(f"\n❌ 所有平台均无法下载: {doi}")


# ===== 平台列表命令 =====
def cmd_platforms(args):
    platforms = discover_platforms()
    print(f"📚 可用平台 ({len(platforms)}):")
    for name in sorted(platforms.keys()):
        print(f"  ✅ {name}")


# ===== 期刊列表命令 =====
def cmd_journals(args):
    try:
        from domain import TRANSPORT_JOURNALS
    except ImportError:
        print("❌ 交通领域模块未加载")
        return
    print(f"📚 交通领域期刊 ({len(TRANSPORT_JOURNALS)}):")
    seen = set()
    for name, full, abbr, issn in TRANSPORT_JOURNALS:
        if name not in seen:
            seen.add(name)
            print(f"  {abbr:30s} | {name}")


# ===== 主入口 =====
def main():
    parser = argparse.ArgumentParser(
        description="PaperHub - 一站式学术论文搜索与下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  paperhub search "attention is all you need"
  paperhub search "bus rapid transit" --transport --limit 5
  paperhub search "deep learning" --journal "trr" --limit 3 --export bibtex
  paperhub download 10.48550/arXiv.1706.03762
  paperhub download --search "transformer" --limit 3
  paperhub download --from-file doids.txt
  paperhub platforms
  paperhub journals
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # search
    search_parser = subparsers.add_parser("search", help="搜索论文")
    search_parser.add_argument("query", nargs="?", default="", help="搜索关键词")
    search_parser.add_argument("--platforms", "-p", nargs="+", help="指定平台（逗号分隔）")
    search_parser.add_argument("--all", "-a", action="store_true", help="搜索所有平台")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="返回数量")
    search_parser.add_argument("--json", action="store_true", help="JSON 输出")
    search_parser.add_argument("--export", "-e", choices=["bibtex", "csv"], help="导出格式")
    search_parser.add_argument("--transport", "-t", action="store_true", help="交通领域搜索")
    search_parser.add_argument("--journal", "-j", help="按期刊过滤（模糊匹配）")
    search_parser.add_argument("--sort", choices=["year", "title", "relevance"], default="relevance", help="排序方式")
    search_parser.add_argument("--year-from", type=str, help="起始年份")
    search_parser.add_argument("--year-to", type=str, help="结束年份")
    search_parser.add_argument("--author", type=str, help="作者过滤")
    search_parser.add_argument("--list-journals", action="store_true", help="列出交通期刊")

    # download
    download_parser = subparsers.add_parser("download", help="下载论文")
    download_parser.add_argument("doi", nargs="?", help="DOI 或 arXiv ID")
    download_parser.add_argument("--search", "-s", help="搜索+下载")
    download_parser.add_argument("--from-file", "-f", help="从文件读取 DOI 列表")
    download_parser.add_argument("--limit", "-l", type=int, help="搜索+下载篇数")
    download_parser.add_argument("--json", action="store_true", help="JSON 输出")

    # platforms
    subparsers.add_parser("platforms", help="列出可用平台")

    # journals
    subparsers.add_parser("journals", help="列出交通期刊")

    args = parser.parse_args()

    if args.command == "search":
        if args.list_journals and not args.query:
            cmd_journals(args)
            return
        if not args.query and not args.list_journals:
            search_parser.print_help()
            return
        cmd_search(args)
    elif args.command == "download":
        if not args.doi and not args.search and not args.from_file:
            download_parser.print_help()
            return
        cmd_download(args)
    elif args.command == "platforms":
        cmd_platforms(args)
    elif args.command == "journals":
        cmd_journals(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()