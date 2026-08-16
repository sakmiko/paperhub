#!/usr/bin/env python3
"""
PaperHub - 一站式学术论文搜索与下载工具 (插件化重构)

Usage:
  paperhub search "attention is all you need"
  paperhub search "transformer" --platforms arxiv,crossref --limit 10
  paperhub search "bus rapid transit" --transport --limit 5
  paperhub download 10.48550/arXiv.1706.03762
  paperhub platforms
  paperhub plugins
  paperhub history
  paperhub bookmark <doi>
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
    PaperResult, download_pdf, safe_filename,
    dedup_results, sort_results, filter_results,
    format_results, export_bibtex, export_csv,
)
from platforms import BasePlatform

DOWNLOAD_PRIORITY = [
    "arxiv", "pubmed", "openalex", "semantic-scholar", "core",
    "doaj", "zenodo", "biorxiv", "bohrium",
    "crossref", "sci-hub", "cnki", "google-scholar", "ssrn",
]


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


def try_download_parallel(platforms: dict, paper: PaperResult, priority: List[str] = None) -> Optional[str]:
    if priority is None:
        priority = DOWNLOAD_PRIORITY
    filename = safe_filename(paper.title or paper.doi or "paper")
    for name in priority:
        if name not in platforms:
            continue
        result = try_download_single(platforms[name], paper, filename)
        if result:
            # 触发 on_download hook
            import plugins as plugin_sys
            result = plugin_sys.run_hook("on_download", paper, result)
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


def do_search(query: str, platforms: dict, limit: int = 10, silent: bool = False) -> list:
    """统一搜索入口，支持插件 hook"""
    import plugins as plugin_sys

    # 检查是否有并发搜索插件拦截
    hook_result = plugin_sys.run_hook("search_platforms", query, limit, platforms)
    if hook_result is not None:
        if isinstance(hook_result, tuple):
            all_results, errors = hook_result
        else:
            all_results, errors = hook_result, []
        if not silent and errors:
            for e in errors[:3]:
                print(f"  ⚠️ {e}")
    else:
        # 默认串行搜索
        all_results = []
        for name, platform in platforms.items():
            try:
                results = platform.search(query, limit=limit)
                if results:
                    all_results.extend(results)
                    if not silent:
                        print(f"  ✅ [{name}] 找到 {len(results)} 篇")
            except Exception as e:
                if not silent:
                    print(f"  ⚠️ [{name}] 失败: {e}")
            time.sleep(0.2)

    # 去重排序
    all_results = dedup_results(all_results)

    # 触发 on_search hook（历史记录等）
    all_results = plugin_sys.run_hook("on_search", query, all_results)

    return all_results


# ===== CLI 命令 =====

def cmd_search(args):
    import plugins as plugin_sys

    # 交通领域搜索
    if args.transport or args.journal:
        from domain import search_transport, fuzzy_match_journal, TRANSPORT_JOURNALS

        if args.journal:
            matched = fuzzy_match_journal(args.journal)
            if not matched:
                print(f"❌ 未匹配到期刊: {args.journal}")
                return
            if not args.json:
                print(f"📚 匹配期刊: {', '.join(matched[:5])}")

        results = search_transport(args.query, journal=args.journal, limit=args.limit)
        if not results:
            print("❌ 未找到相关论文")
            return

        paper_results = [PaperResult(
            title=r.get("title", ""), authors=r.get("authors", []),
            doi=r.get("doi", ""), year=r.get("year", ""),
            source=r.get("journal", ""), url=r.get("url", ""),
            platform=r.get("platform", "crossref"),
        ) for r in results]

        paper_results = dedup_results(paper_results)
        paper_results = plugin_sys.run_hook("on_search", args.query, paper_results)

        if args.sort:
            paper_results = sort_results(paper_results, by=args.sort)
        if args.year_from or args.year_to or args.author:
            paper_results = filter_results(paper_results, args.year_from, args.year_to, args.author)

        _output(paper_results, args)
        return

    # 普通搜索
    platforms = get_platforms(args.platforms, args.all)
    if not platforms:
        print("❌ 没有可用的平台")
        sys.exit(1)

    all_results = do_search(args.query, platforms, limit=args.limit, silent=args.json)

    if args.sort:
        all_results = sort_results(all_results, by=args.sort)
    if args.year_from or args.year_to or args.author:
        all_results = filter_results(all_results, args.year_from, args.year_to, args.author)

    _output(all_results, args)


def _output(results, args):
    if args.json:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    elif args.export == "bibtex":
        print(export_bibtex(results))
    elif args.export == "csv":
        print(export_csv(results))
    else:
        print(f"\n{'='*50}")
        print(f"共 {len(results)} 篇结果")
        print(format_results(results, "text"))


def cmd_download(args):
    platforms = get_platforms(all_platforms=True)
    if not platforms:
        print("❌ 没有可用的平台")
        sys.exit(1)

    if args.search:
        print(f"🔍 搜索: {args.search}")
        results = do_search(args.search, platforms, limit=args.limit or 5, silent=True)
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
                    print(f"  ✅ [{name}] {info.title[:60]}")
                    break
        except Exception:
            pass

    arxiv_result = try_download_arxiv_id(doi, platforms)
    if arxiv_result:
        paper = arxiv_result

    path = try_download_parallel(platforms, paper)

    if args.json:
        print(json.dumps({"doi": doi, "title": paper.title, "success": path is not None, "path": path or ""}, ensure_ascii=False, indent=2))
    elif path:
        print(f"\n✅ 下载成功: {path}")
    else:
        print(f"\n❌ 所有平台均无法下载: {doi}")


def cmd_platforms(args):
    platforms = discover_platforms()
    print(f"📚 可用平台 ({len(platforms)}):")
    for name in sorted(platforms.keys()):
        print(f"  ✅ {name}")


def cmd_journals(args):
    from domain import TRANSPORT_JOURNALS
    print(f"📚 交通领域期刊 ({len(TRANSPORT_JOURNALS)}):")
    seen = set()
    for name, full, abbr, issn, aliases in TRANSPORT_JOURNALS:
        if name not in seen:
            seen.add(name)
            print(f"  {abbr:30s} | {name}")


def cmd_plugins(args):
    import plugins as plugin_sys
    info = plugin_sys.list_plugins()
    if not info:
        print("没有已注册的插件")
        return
    print(f"🔌 插件列表 ({len(info)}):\n")
    for p in info:
        icon = "✅" if p["enabled"] else "⬜"
        avail = "" if p["available"] else " (依赖未安装)"
        deps = f"  [requires: {', '.join(p['requires'])}]" if p["requires"] else ""
        print(f"  {icon} {p['name']:20s} — {p['description']}{avail}{deps}")


def cmd_history(args):
    import plugins as plugin_sys
    p = plugin_sys.get("history")
    if not p or not p.enabled:
        print("❌ 历史记录插件未启用")
        return
    rows = p.get_history(limit=args.limit or 20)
    if not rows:
        print("📭 没有搜索历史")
        return
    print(f"📋 搜索历史 (最近 {len(rows)} 条):\n")
    for r in rows:
        print(f"  [{r['created_at']}] {r['query']} ({r['results_count']}篇)")


def cmd_bookmark(args):
    import plugins as plugin_sys
    p = plugin_sys.get("history")
    if not p or not p.enabled:
        print("❌ 历史记录插件未启用")
        return

    if args.action == "list":
        rows = p.list_bookmarks()
        if not rows:
            print("📭 没有收藏")
            return
        print(f"⭐ 收藏夹 ({len(rows)}):\n")
        for r in rows:
            print(f"  [{r['year']}] {r['title'][:60]}")
            print(f"       DOI: {r['doi']}")
    elif args.action == "add":
        platforms = get_platforms(all_platforms=True)
        doi = normalize_doi(args.doi)
        paper = PaperResult(doi=doi, title=doi)
        for name in DOWNLOAD_PRIORITY:
            if name not in platforms:
                continue
            try:
                info = platforms[name].fetch_by_doi(doi)
                if info and info.title:
                    paper = info
                    break
            except Exception:
                pass
        if p.add_bookmark(paper):
            print(f"⭐ 已收藏: {paper.title[:60]}")
        else:
            print(f"❌ 收藏失败（需要 DOI）")
    elif args.action == "remove":
        if p.remove_bookmark(args.doi):
            print(f"🗑️ 已移除: {args.doi}")
        else:
            print(f"❌ 未找到: {args.doi}")


def main():
    # 初始化插件系统
    import plugins as plugin_sys
    plugin_sys.auto_discover()
    plugin_sys.init_all()

    parser = argparse.ArgumentParser(
        description="PaperHub - 一站式学术论文搜索与下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  paperhub search "attention is all you need"
  paperhub search "bus rapid transit" --transport --limit 5
  paperhub search "deep learning" --journal "trr" --export bibtex
  paperhub download 10.48550/arXiv.1706.03762
  paperhub download --search "transformer" --limit 3
  paperhub platforms
  paperhub plugins
  paperhub history
  paperhub bookmark list
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # search
    sp = subparsers.add_parser("search", help="搜索论文")
    sp.add_argument("query", nargs="?", default="", help="搜索关键词")
    sp.add_argument("--platforms", "-p", nargs="+", help="指定平台")
    sp.add_argument("--all", "-a", action="store_true", help="搜索所有平台")
    sp.add_argument("--limit", "-l", type=int, default=10, help="返回数量")
    sp.add_argument("--json", action="store_true", help="JSON 输出")
    sp.add_argument("--export", "-e", choices=["bibtex", "csv"], help="导出格式")
    sp.add_argument("--transport", "-t", action="store_true", help="交通领域搜索")
    sp.add_argument("--journal", "-j", help="按期刊过滤")
    sp.add_argument("--sort", choices=["year", "title", "relevance"], default="relevance")
    sp.add_argument("--year-from", type=str)
    sp.add_argument("--year-to", type=str)
    sp.add_argument("--author", type=str)

    # download
    dp = subparsers.add_parser("download", help="下载论文")
    dp.add_argument("doi", nargs="?", help="DOI 或 arXiv ID")
    dp.add_argument("--search", "-s", help="搜索+下载")
    dp.add_argument("--from-file", "-f", help="从文件读取 DOI 列表")
    dp.add_argument("--limit", "-l", type=int, help="搜索+下载篇数")
    dp.add_argument("--json", action="store_true", help="JSON 输出")

    # platforms
    subparsers.add_parser("platforms", help="列出可用平台")

    # journals
    subparsers.add_parser("journals", help="列出交通期刊")

    # plugins
    subparsers.add_parser("plugins", help="列出插件状态")

    # history
    hp = subparsers.add_parser("history", help="搜索历史")
    hp.add_argument("--limit", "-l", type=int, default=20)

    # bookmark
    bp = subparsers.add_parser("bookmark", help="论文收藏夹")
    bp.add_argument("action", choices=["list", "add", "remove"])
    bp.add_argument("doi", nargs="?", help="DOI")

    args = parser.parse_args()

    if args.command == "search":
        if not args.query:
            sp.print_help()
            return
        cmd_search(args)
    elif args.command == "download":
        if not args.doi and not args.search and not args.from_file:
            dp.print_help()
            return
        cmd_download(args)
    elif args.command == "platforms":
        cmd_platforms(args)
    elif args.command == "journals":
        cmd_journals(args)
    elif args.command == "plugins":
        cmd_plugins(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "bookmark":
        cmd_bookmark(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
