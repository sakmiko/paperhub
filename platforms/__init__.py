"""平台基类"""
from abc import ABC, abstractmethod
from typing import List, Optional

# 兼容相对导入和直接导入
try:
    from ..core.utils import PaperResult
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from core.utils import PaperResult


class BasePlatform(ABC):
    """所有论文平台的基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """平台名称（唯一标识符）"""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10, **kwargs) -> List[PaperResult]:
        """按关键词搜索论文"""
        pass

    @abstractmethod
    def fetch_by_doi(self, doi: str) -> Optional[PaperResult]:
        """按 DOI 获取论文信息"""
        pass

    def download(self, paper: PaperResult) -> Optional[str]:
        """下载论文 PDF（可选实现）"""
        return None