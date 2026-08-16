"""SQLite local cache for paper search results."""
import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .utils import PaperResult

# Default cache DB path (relative to project root)
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "paper_cache.db"


class Cache:
    """SQLite-backed cache for paper search results and metadata.

    Thread-safe: uses a reentrant lock so nested calls (e.g. save_search
    calling save_paper internally) won't deadlock.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS searches (
                    query_hash TEXT NOT NULL,
                    platform   TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (query_hash, platform)
                );

                CREATE TABLE IF NOT EXISTS papers (
                    doi        TEXT PRIMARY KEY,
                    title      TEXT NOT NULL DEFAULT '',
                    authors    TEXT NOT NULL DEFAULT '[]',
                    year       TEXT NOT NULL DEFAULT '',
                    source     TEXT NOT NULL DEFAULT '',
                    url        TEXT NOT NULL DEFAULT '',
                    pdf_url    TEXT NOT NULL DEFAULT '',
                    abstract   TEXT NOT NULL DEFAULT '',
                    platform   TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_searches_created
                    ON searches(created_at);
                CREATE INDEX IF NOT EXISTS idx_papers_platform
                    ON papers(platform);
            """)
            self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # Search cache
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_query(query: str) -> str:
        """Return a stable SHA-256 hex digest of the normalized query."""
        normalized = query.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def save_search(self, query: str, platform: str,
                    results: List[PaperResult]) -> None:
        """Cache search results for a (query, platform) pair.

        Also upserts each individual paper into the ``papers`` table so
        metadata lookups by DOI work even without re-running a search.
        """
        query_hash = self._hash_query(query)
        results_json = json.dumps(
            [r.to_dict() for r in results],
            ensure_ascii=False,
        )

        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO searches
                       (query_hash, platform, results_json, created_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (query_hash, platform, results_json),
            )
            # Upsert individual papers so they're findable by DOI
            for paper in results:
                self._upsert_paper(paper)
            self.conn.commit()

    def get_search(self, query: str, platform: str,
                   max_age_hours: int = 24) -> List[PaperResult]:
        """Return cached search results if they are younger than
        ``max_age_hours``, otherwise return an empty list.
        """
        query_hash = self._hash_query(query)

        with self._lock:
            row = self.conn.execute(
                """SELECT results_json, created_at
                   FROM searches
                   WHERE query_hash = ? AND platform = ?""",
                (query_hash, platform),
            ).fetchone()

        if row is None:
            return []

        age = _age_hours(row["created_at"])
        if age > max_age_hours:
            return []

        return _json_to_results(row["results_json"])

    # ------------------------------------------------------------------
    # Individual paper cache
    # ------------------------------------------------------------------

    def save_paper(self, paper: PaperResult) -> None:
        """Cache (or update) an individual paper's metadata, dedup by DOI."""
        with self._lock:
            self._upsert_paper(paper)
            self.conn.commit()

    def get_paper(self, doi: str) -> Optional[PaperResult]:
        """Retrieve a single paper by its DOI.

        Returns ``None`` if the DOI is not in the cache.
        """
        if not doi:
            return None
        doi = doi.strip().lower()

        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM papers WHERE doi = ?", (doi,)
            ).fetchone()

        if row is None:
            return None
        return _row_to_paper(row)

    def _upsert_paper(self, paper: PaperResult) -> None:
        """Insert or replace a single paper row (caller holds lock)."""
        doi = (paper.doi or "").strip().lower()
        if not doi:
            return  # skip papers without a DOI

        self.conn.execute(
            """INSERT OR REPLACE INTO papers
                   (doi, title, authors, year, source, url, pdf_url,
                    abstract, platform, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       COALESCE((SELECT created_at FROM papers WHERE doi = ?),
                                datetime('now')))""",
            (
                doi,
                paper.title or "",
                json.dumps(paper.authors, ensure_ascii=False),
                paper.year or "",
                paper.source or "",
                paper.url or "",
                paper.pdf_url or "",
                paper.abstract or "",
                paper.platform or "",
                doi,  # used in the COALESCE subquery to keep original created_at
            ),
        )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return cache statistics.

        Returns:
            dict with keys:
                - total_papers (int)
                - cached_searches (int)
                - oldest_entry (str | None) — ISO datetime of the oldest
                  cached search, or None if empty
        """
        with self._lock:
            total_papers = self.conn.execute(
                "SELECT COUNT(*) FROM papers"
            ).fetchone()[0]

            cached_searches = self.conn.execute(
                "SELECT COUNT(*) FROM searches"
            ).fetchone()[0]

            oldest = self.conn.execute(
                "SELECT MIN(created_at) FROM searches"
            ).fetchone()[0]

        return {
            "total_papers": total_papers,
            "cached_searches": cached_searches,
            "oldest_entry": oldest,
        }


# ======================================================================
# Internal helpers
# ======================================================================


def _age_hours(created_at: str) -> float:
    """Return the number of hours between *created_at* (ISO datetime string)
    and now.

    Returns infinity on parse failure so the caller treats the row as
    expired rather than crashing.
    """
    try:
        dt = datetime.fromisoformat(created_at)
    except (ValueError, TypeError):
        return float("inf")

    # If the stored datetime has no timezone info, treat it as UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600


def _json_to_results(json_str: str) -> List[PaperResult]:
    """Deserialize a JSON array of paper dicts back to ``PaperResult``
    objects.
    """
    try:
        items = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []
    return [PaperResult(**item) for item in items if isinstance(item, dict)]


def _row_to_paper(row: sqlite3.Row) -> PaperResult:
    """Convert a ``papers`` table row to a ``PaperResult``."""
    authors = json.loads(row["authors"]) if row["authors"] else []
    return PaperResult(
        title=row["title"],
        authors=authors,
        doi=row["doi"],
        year=row["year"],
        source=row["source"],
        url=row["url"],
        pdf_url=row["pdf_url"],
        abstract=row["abstract"],
        platform=row["platform"],
    )