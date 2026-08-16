"""PaperHub Web 界面（可选，通过 Flask 提供）

启动方式: python -m web.app
依赖: pip install flask
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from flask import Flask, render_template, request, jsonify, send_from_directory
except ImportError:
    print("❌ 需要 Flask: pip install flask")
    sys.exit(1)

from core.utils import PaperResult, dedup_results, sort_results, filter_results, format_results
from main import discover_platforms, get_platforms, DOWNLOAD_PRIORITY, try_download_parallel

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24).hex()

# 尝试加载缓存
try:
    from core.cache import Cache
    cache = Cache()
except ImportError:
    cache = None


@app.route("/")
def index():
    platforms = discover_platforms()
    return render_template("index.html", platforms=sorted(platforms.keys()))


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "请输入搜索关键词"}), 400

    platform_names = data.get("platforms", [])
    limit = int(data.get("limit", 10))
    transport = data.get("transport", False)
    journal = data.get("journal", "")

    # 尝试从缓存读取
    if cache and not transport:
        cached = []
        for pname in platform_names or list(discover_platforms().keys()):
            cached.extend(cache.get_search(query, pname, max_age_hours=24))
        if cached:
            return jsonify({"results": [r.to_dict() for r in cached], "cached": True})

    platforms = get_platforms(platform_names, all_platforms=(not platform_names))

    if transport or journal:
        try:
            from domain import search_transport, fuzzy_match_journal
            if journal:
                matched = fuzzy_match_journal(journal)
                if not matched:
                    return jsonify({"error": f"未匹配到期刊: {journal}"}), 404
                journal_filter = matched[0]
            else:
                journal_filter = None
            results = search_transport(query, journal=journal_filter, limit=limit)
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
            return jsonify({"results": [r.to_dict() for r in paper_results]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    all_results = []
    for name, platform in platforms.items():
        try:
            results = platform.search(query, limit=limit)
            if results:
                all_results.extend(results)
        except Exception:
            pass

    all_results = dedup_results(all_results)
    year_from = data.get("year_from")
    year_to = data.get("year_to")
    author = data.get("author")
    if year_from or year_to or author:
        all_results = filter_results(all_results, year_from, year_to, author)

    # 写入缓存
    if cache:
        for name in platform_names or list(platforms.keys()):
            cache.save_search(query, name, all_results)

    return jsonify({
        "results": [r.to_dict() for r in all_results],
        "total": len(all_results),
        "cached": False,
    })


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.json or {}
    doi = data.get("doi", "").strip()
    if not doi:
        return jsonify({"error": "请输入 DOI"}), 400

    platforms = get_platforms(all_platforms=True)
    paper = PaperResult(doi=doi)

    for name in DOWNLOAD_PRIORITY:
        if name not in platforms:
            continue
        try:
            info = platforms[name].fetch_by_doi(doi)
            if info and info.title and "Paper DOI" not in info.title:
                paper = info
                break
        except Exception:
            pass

    path = try_download_parallel(platforms, paper)
    if path:
        return jsonify({"success": True, "path": path, "title": paper.title})
    return jsonify({"success": False, "error": "所有平台无法下载"}), 404


@app.route("/api/citation/<doi>", methods=["GET"])
def api_citation(doi):
    try:
        from domain.citation import get_citation_network
        network = get_citation_network(doi)
        return jsonify({
            "paper": network.get("paper", {}).to_dict() if network.get("paper") else {},
            "citations": [r.to_dict() for r in network.get("citations", [])],
            "references": [r.to_dict() for r in network.get("references", [])],
        })
    except ImportError:
        return jsonify({"error": "引用模块未加载"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/summary", methods=["POST"])
def api_summary():
    data = request.json or {}
    try:
        from domain.summary import summarize, is_available
        if not is_available():
            return jsonify({"error": "GLM API 未配置 (设置 GLM_API_KEY)"}), 501
        paper = PaperResult(
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            doi=data.get("doi", ""),
        )
        summary = summarize(paper)
        return jsonify({"summary": summary or ""})
    except ImportError:
        return jsonify({"error": "摘要模块未加载"}), 501


@app.route("/api/cache/stats", methods=["GET"])
def api_cache_stats():
    if not cache:
        return jsonify({"error": "缓存未启用"}), 501
    return jsonify(cache.get_stats())


@app.route("/api/platforms", methods=["GET"])
def api_platforms():
    platforms = discover_platforms()
    return jsonify({"platforms": sorted(platforms.keys()), "count": len(platforms)})


@app.route("/downloads/<path:filename>")
def download_file(filename):
    return send_from_directory(Path.home() / "paper-downloads", filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 PaperHub Web 界面: http://0.0.0.0:{port}")
    print(f"   搜索: curl -X POST http://localhost:{port}/api/search -H 'Content-Type: application/json' -d '{{\"query\":\"attention\"}}'")
    app.run(host="0.0.0.0", port=port, debug=True)