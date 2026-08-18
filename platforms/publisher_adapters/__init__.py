"""出版商适配器注册和分发"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseAdapter(ABC):
    """出版商适配器基类"""
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        pass

    @abstractmethod
    def extract_pdf_url(self, html: str, url: str = "") -> Optional[str]:
        pass


# 延迟导入避免循环依赖
_ADAPTERS = None

def _load_adapters():
    global _ADAPTERS
    if _ADAPTERS is not None:
        return _ADAPTERS
    _ADAPTERS = []
    from .elsevier import ElsevierAdapter
    from .nature import NatureAdapter
    from .wiley import WileyAdapter
    from .springer import SpringerAdapter
    from .generic import GenericAdapter
    _ADAPTERS = [
        ElsevierAdapter(),
        NatureAdapter(),
        WileyAdapter(),
        SpringerAdapter(),
        GenericAdapter(),
    ]
    return _ADAPTERS


def get_adapter(url: str) -> Optional[BaseAdapter]:
    """根据URL返回匹配的适配器"""
    for adapter in _load_adapters():
        try:
            if adapter.can_handle(url):
                return adapter
        except Exception:
            pass
    return None


def extract_pdf_url(html: str, url: str = "") -> Optional[str]:
    """用匹配的适配器从HTML中提取PDF URL"""
    adapter = get_adapter(url)
    if adapter:
        return adapter.extract_pdf_url(html, url)
    return None
