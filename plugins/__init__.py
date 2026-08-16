"""PaperHub 插件系统

所有增强功能以插件形式实现，可在 config.yaml 中开关。
插件不安装依赖时自动跳过，不影响核心功能。

插件生命周期:
  1. auto_discover()  — 自动扫描 plugins/ 目录
  2. init_all()       — 加载配置，初始化可用插件
  3. 插件通过 hooks 注入功能

可用 hooks:
  - on_search(query, results)   — 搜索后处理（如历史记录）
  - on_download(paper, path)     — 下载后处理（如PDF元数据、Zotero推送）
  - get_proxy()                 — 返回代理配置
  - search_platforms(query, limit, platforms) — 并发搜索
"""
import importlib
import os
import pkgutil
from typing import Dict, List, Optional, Any, Callable

from core.config import DOWNLOAD_DIR, TIMEOUT


class Plugin:
    """插件基类。子类只需实现 name/description 和需要的方法。"""
    name: str = ""
    description: str = ""
    requires: List[str] = []  # pip 依赖包名列表

    def __init__(self):
        self._enabled: Optional[bool] = None
        self._config: dict = {}

    @property
    def enabled(self) -> bool:
        if self._enabled is not None:
            return self._enabled
        return self.is_available()

    def is_available(self) -> bool:
        """检查依赖是否满足"""
        for dep in self.requires:
            try:
                importlib.import_module(dep)
            except ImportError:
                return False
        return True

    def setup(self, config: dict) -> None:
        """初始化插件"""
        self._config = config or {}
        self._enabled = True

    def teardown(self) -> None:
        """清理资源"""
        self._enabled = False

    # === Hooks（子类按需覆盖）===

    def on_search(self, query: str, results: list) -> list:
        """搜索后处理，返回（可能修改的）结果"""
        return results

    def on_download(self, paper, path: str) -> str:
        """下载后处理，返回（可能修改的）路径"""
        return path

    def get_proxy(self) -> Optional[dict]:
        """返回代理配置"""
        return None

    def search_platforms(self, query: str, limit: int, platforms: dict) -> Optional[list]:
        """并发/自定义搜索，返回 PaperResult 列表。None=使用默认串行搜索。"""
        return None  # None = 不拦截，走默认


# === 全局注册表 ===

_registry: Dict[str, Plugin] = {}
_config: dict = {}
_hooks: Dict[str, List[Plugin]] = {}


def register(plugin: Plugin) -> Plugin:
    """注册插件"""
    if not plugin.name:
        raise ValueError("Plugin must have a name")
    _registry[plugin.name] = plugin
    return plugin


def get(name: str) -> Optional[Plugin]:
    return _registry.get(name)


def all_plugins() -> Dict[str, Plugin]:
    return dict(_registry)


def enabled_plugins() -> Dict[str, Plugin]:
    return {k: v for k, v in _registry.items() if v.enabled}


def list_plugins() -> List[dict]:
    """返回插件状态列表"""
    return [
        {
            "name": p.name,
            "description": p.description,
            "enabled": p.enabled,
            "available": p.is_available(),
            "requires": p.requires,
        }
        for p in _registry.values()
    ]


def load_config(config_path: Optional[str] = None) -> dict:
    """加载插件配置"""
    global _config
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config.yaml"
        )
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            full = yaml.safe_load(f) or {}
        _config = full.get("plugins", {})
    except Exception:
        _config = {}
    return _config


def is_plugin_enabled(name: str) -> bool:
    """从配置检查插件是否启用"""
    plugin_cfg = _config.get(name, {})
    if isinstance(plugin_cfg, dict):
        return plugin_cfg.get("enabled", True)
    return bool(plugin_cfg)


def init_all() -> None:
    """初始化所有已注册且可用的插件"""
    global _hooks
    load_config()
    _hooks.clear()
    for name, plugin in _registry.items():
        plugin_cfg = _config.get(name, {})
        enabled_in_config = is_plugin_enabled(name)
        if plugin.is_available() and enabled_in_config:
            try:
                plugin.setup(plugin_cfg if isinstance(plugin_cfg, dict) else {})
            except Exception as e:
                print(f"  ⚠️ 插件 [{name}] 初始化失败: {e}")
                plugin._enabled = False
                continue
            # 注册 hooks
            for hook_name in ["on_search", "on_download", "get_proxy", "search_platforms"]:
                method = getattr(plugin, hook_name, None)
                if method and callable(method):
                    _hooks.setdefault(hook_name, []).append(plugin)
        else:
            plugin._enabled = False


def auto_discover() -> None:
    """自动发现并注册 plugins/ 目录下的所有插件模块"""
    import plugins as pkg
    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_") or ispkg:
            continue
        try:
            importlib.import_module(f"plugins.{modname}")
        except Exception as e:
            pass  # 静默跳过导入失败的插件


# === Hook 调用 ===

def run_hook(name: str, *args, **kwargs):
    """执行某个 hook 的所有插件，返回结果"""
    plugins_with_hook = _hooks.get(name, [])
    if name == "search_platforms":
        # 搜索拦截：第一个返回非None结果的插件生效
        for p in plugins_with_hook:
            try:
                result = p.search_platforms(*args, **kwargs)
                if result is not None:
                    return result
            except Exception:
                pass
        return None
    elif name == "get_proxy":
        # 代理：第一个返回非None的插件生效
        for p in plugins_with_hook:
            try:
                proxy = p.get_proxy()
                if proxy is not None:
                    return proxy
            except Exception:
                pass
        return None
    elif name == "on_search":
        # 搜索后处理：链式调用
        results = args[1] if len(args) > 1 else kwargs.get("results", [])
        query = args[0] if args else kwargs.get("query", "")
        for p in plugins_with_hook:
            try:
                results = p.on_search(query, results) or results
            except Exception:
                pass
        return results
    elif name == "on_download":
        # 下载后处理：链式调用
        path = args[1] if len(args) > 1 else kwargs.get("path", "")
        paper = args[0] if args else kwargs.get("paper")
        for p in plugins_with_hook:
            try:
                path = p.on_download(paper, path) or path
            except Exception:
                pass
        return path
    return None
