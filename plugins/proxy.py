"""代理支持插件 — 从 config.yaml 读取代理配置，注入到 HTTP 请求"""
from typing import Optional

from plugins import Plugin, register


class ProxyPlugin(Plugin):
    name = "proxy"
    description = "HTTP 代理支持：config.yaml 配置 proxy URL，自动注入 fetch/download"
    requires = []

    def setup(self, config: dict) -> None:
        super().setup(config)
        self._proxy_url = config.get("url", "")
        self._no_proxy = config.get("no_proxy", "localhost,127.0.0.1")

    def get_proxy(self) -> Optional[dict]:
        if not self._proxy_url:
            return None
        return {
            "http": self._proxy_url,
            "https": self._proxy_url,
            "no_proxy": self._no_proxy,
        }

    def on_search(self, query: str, results: list) -> list:
        """注入代理到 core.utils 的 fetch/post 函数"""
        if not self._proxy_url:
            return results

        try:
            import core.utils as utils
            import requests

            # 备份原始函数
            if not hasattr(utils, "_original_fetch"):
                utils._original_fetch = utils.fetch
                utils._original_post = utils.post

            proxy = self.get_proxy()

            def _patched_fetch(url, headers=None, params=None, timeout=utils.TIMEOUT, retries=3):
                h = {"User-Agent": utils.USER_AGENT}
                if headers:
                    h.update(headers)
                for i in range(retries):
                    try:
                        resp = requests.get(url, headers=h, params=params, timeout=timeout, proxies=proxy)
                        if resp.status_code == 429:
                            import time; time.sleep(5)
                            continue
                        return resp
                    except requests.RequestException:
                        if i == retries - 1:
                            return None
                        import time; time.sleep(2)
                return None

            def _patched_post(url, json_data, headers=None, timeout=utils.TIMEOUT, retries=3):
                h = {"User-Agent": utils.USER_AGENT, "Content-Type": "application/json"}
                if headers:
                    h.update(headers)
                for i in range(retries):
                    try:
                        resp = requests.post(url, json=json_data, headers=h, timeout=timeout, proxies=proxy)
                        if resp.status_code == 429:
                            import time; time.sleep(5)
                            continue
                        return resp
                    except requests.RequestException:
                        if i == retries - 1:
                            return None
                        import time; time.sleep(2)
                return None

            utils.fetch = _patched_fetch
            utils.post = _patched_post
        except Exception:
            pass

        return results


register(ProxyPlugin())
