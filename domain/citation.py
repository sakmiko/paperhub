"""Citation network analysis module

Provides functions to retrieve forward citations, backward references,
citation networks, and citation counts via Semantic Scholar and OpenAlex APIs.
"""

import sys
import os
import time
from typing import List, Optional, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.utils import PaperResult, fetch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"

_S2_FIELDS = "title,authors,year,externalIds"
"""Fields requested from the Semantic Scholar API for citation/reference items."""

_S2_PAPER_FIELDS = "title,authors,year,externalIds,venue,abstract,url,openAccessPdf"
"""Fields requested when fetching a full paper record."""


def _parse_s2_paper(item: dict) -> Optional[PaperResult]:
    """Parse a Semantic Scholar paper dictionary into a PaperResult."""
    if not item or not item.get("title"):
        return None
    title = item.get("title", "")
    authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
    ext_ids = item.get("externalIds", {}) or {}
    doi = ext_ids.get("DOI", "")
    year = str(item.get("year", "")) if item.get("year") is not None else ""
    return PaperResult(
        title=title,
        authors=authors[:5],
        doi=doi,
        year=year,
        platform="semantic-scholar",
    )


def _fetch_s2_citations_or_references(
    doi: str,
    endpoint: str,         # "citations" or "references"
    paper_key: str,        # "citingPaper" or "citedPaper"
    limit: int = 10,
) -> List[PaperResult]:
    """
    Fetch forward citations (paper_key="citingPaper") or backward references
    (paper_key="citedPaper") from the Semantic Scholar API.
    """
    url = f"{_S2_BASE}/DOI:{doi}/{endpoint}"
    params = {
        "fields": _S2_FIELDS,
        "limit": min(limit, 100),
    }

    for attempt in range(3):
        resp = fetch(url, params=params, timeout=20)
        if resp is None:
            # fetch already slept 2s on network error; back off a bit more
            time.sleep(3)
            continue
        if resp.status_code == 429:
            time.sleep(10)
            continue
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except Exception:
            return []
        results = []
        for entry in data.get("data", []):
            paper_data = entry.get(paper_key)
            parsed = _parse_s2_paper(paper_data)
            if parsed is not None:
                results.append(parsed)
        return results
    return []


def _fetch_paper(doi: str) -> Optional[PaperResult]:
    """Fetch a single paper record by DOI from Semantic Scholar."""
    url = f"{_S2_BASE}/DOI:{doi}"
    params = {"fields": _S2_PAPER_FIELDS}
    for attempt in range(3):
        resp = fetch(url, params=params, timeout=20)
        if resp is None:
            time.sleep(3)
            continue
        if resp.status_code == 429:
            time.sleep(10)
            continue
        if resp.status_code != 200:
            return None
        try:
            item = resp.json()
        except Exception:
            return None
        title = item.get("title", "")
        if not title:
            return None
        authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
        ext_ids = item.get("externalIds", {}) or {}
        doi_val = ext_ids.get("DOI", "")
        year = str(item.get("year", "")) if item.get("year") is not None else ""
        pdf_info = item.get("openAccessPdf", {}) or {}
        pdf_url = pdf_info.get("url", "") if pdf_info else ""
        abstract = item.get("abstract", "") or ""
        return PaperResult(
            title=title,
            authors=authors[:5],
            doi=doi_val,
            year=year,
            source=item.get("venue", ""),
            url=item.get("url", ""),
            pdf_url=pdf_url,
            abstract=abstract[:500],
            platform="semantic-scholar",
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_citations(doi: str, limit: int = 10) -> List[PaperResult]:
    """Get papers that cite *doi* (forward citations).

    Uses the Semantic Scholar API endpoint:
        GET /graph/v1/paper/DOI:{doi}/citations

    Returns a list of PaperResult objects.  On failure an empty list is
    returned.
    """
    return _fetch_s2_citations_or_references(
        doi, endpoint="citations", paper_key="citingPaper", limit=limit,
    )


def get_references(doi: str, limit: int = 10) -> List[PaperResult]:
    """Get papers referenced by *doi* (backward citations).

    Uses the Semantic Scholar API endpoint:
        GET /graph/v1/paper/DOI:{doi}/references

    Returns a list of PaperResult objects.  On failure an empty list is
    returned.
    """
    return _fetch_s2_citations_or_references(
        doi, endpoint="references", paper_key="citedPaper", limit=limit,
    )


def get_citation_network(doi: str, depth: int = 1) -> Dict[str, Any]:
    """Get the citation network for a paper identified by *doi*.

    At ``depth=1`` (the only supported depth) the returned dictionary has
    the following keys:

        paper       -- PaperResult for the given DOI
        citations   -- list of PaperResult objects (forward citations)
        references  -- list of PaperResult objects (backward references)

    If the paper itself cannot be fetched, ``paper`` is ``None`` and the
    citation/reference lists are empty.
    """
    paper = _fetch_paper(doi)
    if paper is None:
        return {"paper": None, "citations": [], "references": []}

    citations = get_citations(doi, limit=10)
    references = get_references(doi, limit=10)

    return {
        "paper": paper,
        "citations": citations,
        "references": references,
    }


def get_citation_count(doi: str) -> int:
    """Get the number of times *doi* has been cited.

    Tries Semantic Scholar first (``citationCount`` field), then falls back
    to OpenAlex (``cited_by_count`` field).  Returns 0 on failure.
    """
    # ---- Semantic Scholar ----
    url = f"{_S2_BASE}/DOI:{doi}"
    params = {"fields": "citationCount"}
    for attempt in range(2):
        resp = fetch(url, params=params, timeout=15)
        if resp is None:
            continue
        if resp.status_code == 429:
            time.sleep(5)
            continue
        if resp.status_code == 200:
            try:
                data = resp.json()
                count = data.get("citationCount")
                if count is not None:
                    return int(count)
            except Exception:
                pass
        break

    # ---- OpenAlex fallback ----
    try:
        resp = fetch(
            f"https://api.openalex.org/works/doi:{doi}",
            timeout=15,
        )
        if resp and resp.status_code == 200:
            data = resp.json()
            count = data.get("cited_by_count")
            if count is not None:
                return int(count)
    except Exception:
        pass

    return 0