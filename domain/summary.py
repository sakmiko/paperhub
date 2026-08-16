"""GLM 摘要翻译模块（可选，需要 API Key）

通过智谱 GLM-4.7-Flash 对论文进行摘要提取和翻译。
功能可选：无 API Key 时自动跳过。
"""
import json
import os
import re
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
from core.utils import PaperResult, fetch


# GLM API 配置（从环境变量读取）
GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def is_available() -> bool:
    """检查 GLM API 是否可用"""
    return bool(GLM_API_KEY)


def _call_glm(prompt: str, system: str = "你是一个科研助手。") -> Optional[str]:
    """调用 GLM API"""
    if not GLM_API_KEY:
        return None
    import requests
    try:
        resp = requests.post(
            GLM_API_URL,
            headers={
                "Authorization": f"Bearer {GLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "GLM-4.7-Flash",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None


def summarize(paper: PaperResult, lang: str = "zh") -> Optional[str]:
    """提取论文摘要（中文或英文）"""
    if not is_available() or not paper.abstract and not paper.title:
        return None

    text = paper.abstract or paper.title or ""
    lang_name = "中文" if lang == "zh" else "English"
    prompt = f"""请用{lang_name}总结以下论文的核心内容，控制在200字以内：

标题: {paper.title}
摘要: {text[:2000]}

请用{lang_name}输出：1) 研究问题 2) 方法 3) 主要发现"""
    return _call_glm(prompt)


def translate(text: str, target: str = "zh") -> Optional[str]:
    """翻译文本到目标语言"""
    if not is_available() or not text:
        return None
    lang_map = {"zh": "中文", "en": "英文"}
    target_lang = lang_map.get(target, "中文")
    prompt = f"请将以下内容翻译成{target_lang}，保持学术准确性：\n\n{text[:2000]}"
    return _call_glm(prompt)


def extract_keywords(paper: PaperResult) -> Optional[List[str]]:
    """从标题和摘要中提取关键词"""
    if not is_available():
        return None
    text = f"{paper.title}\n{paper.abstract or ''}"
    if not text.strip():
        return None
    prompt = f"""从以下论文信息中提取 3-5 个关键词，用逗号分隔：

{text[:1500]}

输出格式：关键词1, 关键词2, 关键词3"""
    result = _call_glm(prompt)
    if result:
        return [k.strip() for k in result.split(",") if k.strip()]
    return None


def suggest_research_questions(paper: PaperResult) -> Optional[List[str]]:
    """基于论文生成后续研究方向"""
    if not is_available():
        return None
    text = f"{paper.title}\n{paper.abstract or ''}"
    if not text.strip():
        return None
    prompt = f"""基于以下论文，提出 3 个值得进一步研究的开放性问题：

{text[:1500]}

每个问题一行，用数字编号。"""
    result = _call_glm(prompt)
    if result:
        lines = [re.sub(r'^\d+[\.\s]+', '', l).strip() for l in result.split("\n") if l.strip()]
        return lines[:5]
    return None