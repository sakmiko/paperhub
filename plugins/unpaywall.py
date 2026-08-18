"""Unpaywall OA检测插件 — 通过Unpaywall API检测DOI的开放获取版本"""
from typing import Optional

from plugins import Plugin, register


class UnpaywallPlugin(Plugin):
    name = "unpaywall"
    description = "通过Unpaywall API检测DOI的OA版本，优先下载开放获取PDF"
    requires = []
    _api_base = "https://api.unpaywall.org/v2"
    _email = "paperhub@gmail.com"

    def setup(self, config: dict) -> None:
        super().setup(config)
        self._email = config.get("email", "paperhub@gmail.com")

    def check_oa(self, doi: str) -> Optional[dict]:
        """查询Unpaywall API，返回OA信息dict或None"""
        if not doi:
            return None
        from core.utils import fetch
        url = f"{self._api_base}/{doi}?email={self._email}"
        resp = fetch(url, timeout=10, retries=2)
        if not resp or resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        if not data.get("is_oa"):
            return {"is_oa": False}
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf", "") or ""
        html_url = best.get("url", "") or ""
        source = "repository"
        host_type = best.get("host_type", "")
        if "arxiv" in (pdf_url + html_url).lower():
            source = "arxiv"
        elif host_type == "publisher":
            source = "publisher"
        if not pdf_url:
            for loc in data.get("oa_locations") or []:
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break
        return {"is_oa": True, "pdf_url": pdf_url, "html_url": html_url, "source": source}

    def on_download_start(self, paper, platforms):
        """Hook: 下载前查OA，有OA直接返回PDF URL"""
        if not paper.doi:
            return None
        oa = self.check_oa(paper.doi)
        if oa and oa.get("is_oa") and oa.get("pdf_url"):
            return oa["pdf_url"]
        return None


register(UnpaywallPlugin())
