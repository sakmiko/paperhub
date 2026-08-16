"""搜索历史 + 收藏夹插件 — SQLite 存储，CLI 命令支持"""
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from plugins import Plugin, register


class HistoryPlugin(Plugin):
    name = "history"
    description = "搜索历史记录 + 论文收藏夹（SQLite 存储，CLI: paperhub history / paperhub bookmark）"
    requires = []

    def setup(self, config: dict) -> None:
        super().setup(config)
        self._db_path = config.get("db_path", str(Path.home() / ".paperhub" / "history.db"))
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    results_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS bookmarks (
                    doi TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    authors TEXT NOT NULL DEFAULT '[]',
                    year TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            conn.commit()
            conn.close()

    def on_search(self, query: str, results: list) -> list:
        """记录搜索历史"""
        try:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                conn.execute(
                    "INSERT INTO search_history (query, results_count) VALUES (?, ?)",
                    (query, len(results)),
                )
                conn.commit()
                conn.close()
        except Exception:
            pass
        return results

    # === 公共 API ===

    def get_history(self, limit: int = 20) -> list:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM search_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
        return [dict(r) for r in rows]

    def add_bookmark(self, paper) -> bool:
        if not paper.doi:
            return False
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """INSERT OR REPLACE INTO bookmarks (doi, title, authors, year, source, url)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    paper.doi,
                    paper.title or "",
                    json.dumps(paper.authors or [], ensure_ascii=False),
                    paper.year or "",
                    paper.source or "",
                    paper.url or "",
                ),
            )
            conn.commit()
            conn.close()
        return True

    def remove_bookmark(self, doi: str) -> bool:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cur = conn.execute("DELETE FROM bookmarks WHERE doi = ?", (doi,))
            conn.commit()
            deleted = cur.rowcount > 0
            conn.close()
        return deleted

    def list_bookmarks(self) -> list:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM bookmarks ORDER BY created_at DESC"
            ).fetchall()
            conn.close()
        return [dict(r) for r in rows]


register(HistoryPlugin())
