"""并发搜索插件 — ThreadPoolExecutor 并行搜索所有平台"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from plugins import Plugin, register


class ConcurrentSearchPlugin(Plugin):
    name = "concurrent_search"
    description = "并发搜索所有平台，大幅提升搜索速度（14平台串行120s→并发10s）"
    requires = []

    def setup(self, config: dict) -> None:
        super().setup(config)
        self._max_workers = config.get("max_workers", 8)
        self._timeout = config.get("timeout", 30)

    def search_platforms(self, query: str, limit: int, platforms: dict) -> Optional[tuple]:
        """并发搜索所有平台"""
        all_results = []
        errors = []

        def _search_one(name_platform):
            name, platform = name_platform
            try:
                results = platform.search(query, limit=limit)
                return name, results or [], None
            except Exception as e:
                return name, [], str(e)

        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(platforms))) as executor:
            futures = {
                executor.submit(_search_one, (name, plat)): name
                for name, plat in platforms.items()
            }
            for future in as_completed(futures, timeout=self._timeout):
                try:
                    name, results, error = future.result(timeout=self._timeout)
                    if results:
                        all_results.extend(results)
                    if error:
                        errors.append(f"[{name}]: {error}")
                except Exception as e:
                    errors.append(f"[{futures[future]}]: timeout/error: {e}")

        return all_results, errors


register(ConcurrentSearchPlugin())
