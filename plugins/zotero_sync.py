"""Zotero 集成插件 — 搜索结果推送到 Zotero (通过 Better BibTeX API)"""
import json
import os
from typing import Optional

from plugins import Plugin, register


class ZoteroPlugin(Plugin):
    name = "zotero"
    description = "搜索结果推送到 Zotero（需 Zotero 本地运行 + Better BibTeX）"
    requires = ["requests"]

    def setup(self, config: dict) -> None:
        super().setup(config)
        self._api_url = config.get("api_url", "http://localhost:23119")
        self._library = config.get("library", "1")  # library ID
        self._collection = config.get("collection", "")

    def is_available(self) -> bool:
        if not super().is_available():
            return False
        # 检查 Zotero 是否在运行（不阻塞，失败就跳过）
        try:
            import requests
            r = requests.get(f"{self._api_url}/connector/ping", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def on_search(self, query: str, results: list) -> list:
        """搜索结果自动推送到 Zotero"""
        if not results:
            return results

        try:
            import requests
            for paper in results:
                self._push_to_zotero(paper)
        except Exception:
            pass

        return results

    def _push_to_zotero(self, paper) -> bool:
        """单篇论文推送到 Zotero"""
        import requests

        item = {
            "itemType": "journalArticle",
            "title": paper.title or "",
            "creators": [
                {"creatorType": "author", "lastName": a.split()[-1] if " " in a else a,
                 "firstName": " ".join(a.split()[:-1]) if " " in a else ""}
                for a in (paper.authors or [])[:5]
            ],
            "DOI": paper.doi or "",
            "date": paper.year or "",
            "publicationTitle": paper.source or "",
            "url": paper.url or "",
        }

        try:
            r = requests.post(
                f"{self._api_url}/connector/saveItems",
                json={"items": [item], "uri": paper.url or ""},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            return r.status_code == 201
        except Exception:
            return False


register(ZoteroPlugin())
