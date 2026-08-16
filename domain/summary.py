"""LLM 摘要翻译模块（可选，支持任意 OpenAI 兼容 API）

通过配置的 LLM 提供商对论文进行摘要提取和翻译。
功能可选：无 API Key 时自动跳过。

配置方式（环境变量）：
  LLM_API_KEY=your_key              # API Key（必填）
  LLM_API_URL=https://.../v1        # API 地址（可选，默认 GLM）
  LLM_MODEL=glm-4v-plus             # 模型名（可选，默认 GLM-4.7-Flash）
  LLM_PROVIDER=glm|openai|custom    # 提供商标识（可选，自动检测）

示例：
  # GLM (智谱)
  export LLM_API_KEY=your_glm_key

  # OpenAI
  export LLM_API_KEY=sk-xxx
  export LLM_API_URL=https://api.openai.com/v1
  export LLM_MODEL=gpt-4o-mini

  # 自定义 (任何 OpenAI 兼容 API)
  export LLM_API_KEY=xxx
  export LLM_API_URL=https://your-custom-api.com/v1
  export LLM_MODEL=your-model
"""
import json
import os
import re
from typing import List, Optional

import sys, os as _os; sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
from core.utils import PaperResult, fetch

# ===== LLM 配置 =====
# 从环境变量读取，兼容旧版 GLM_API_KEY
LLM_API_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("GLM_API_KEY", "")
LLM_API_URL = os.environ.get("LLM_API_URL", "https://open.bigmodel.cn/api/paas/v4")
LLM_MODEL = os.environ.get("LLM_MODEL", "GLM-4.7-Flash")

# 自动补全 chat/completions 路径
if not LLM_API_URL.endswith("/chat/completions"):
    LLM_API_URL = LLM_API_URL.rstrip("/") + "/chat/completions"


def is_available() -> bool:
    """检查 LLM API 是否已配置"""
    return bool(LLM_API_KEY)


def get_provider_name() -> str:
    """返回当前提供商名称"""
    if "bigmodel" in LLM_API_URL:
        return "GLM (智谱)"
    if "openai" in LLM_API_URL:
        return "OpenAI"
    if "deepseek" in LLM_API_URL:
        return "DeepSeek"
    if "sensenova" in LLM_API_URL:
        return "SenseNova"
    return "Custom LLM"


def _call_llm(prompt: str, system: str = "你是一个科研助手。") -> Optional[str]:
    """调用 LLM API（OpenAI 兼容格式）"""
    if not LLM_API_KEY:
        return None
    import requests
    try:
        resp = requests.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
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
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            # 打印错误信息便于调试
            print(f"  ⚠️ LLM API 错误 ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"  ⚠️ LLM 调用失败: {e}")
    return None


def summarize(paper: PaperResult, lang: str = "zh") -> Optional[str]:
    """提取论文摘要（中文或英文）"""
    if not is_available() or (not paper.abstract and not paper.title):
        return None

    text = paper.abstract or paper.title or ""
    lang_name = "中文" if lang == "zh" else "English"
    prompt = f"""请用{lang_name}总结以下论文的核心内容，控制在200字以内：

标题: {paper.title}
摘要: {text[:2000]}

请用{lang_name}输出：1) 研究问题 2) 方法 3) 主要发现"""
    return _call_llm(prompt)


def translate(text: str, target: str = "zh") -> Optional[str]:
    """翻译文本到目标语言"""
    if not is_available() or not text:
        return None
    lang_map = {"zh": "中文", "en": "英文"}
    target_lang = lang_map.get(target, "中文")
    prompt = f"请将以下内容翻译成{target_lang}，保持学术准确性：\n\n{text[:2000]}"
    return _call_llm(prompt)


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
    result = _call_llm(prompt)
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
    result = _call_llm(prompt)
    if result:
        lines = [re.sub(r'^\d+[\.\s]+', '', l).strip() for l in result.split("\n") if l.strip()]
        return lines[:5]
    return None


def compare_papers(papers: List[PaperResult]) -> Optional[str]:
    """对比多篇论文的异同"""
    if not is_available() or len(papers) < 2:
        return None
    text = ""
    for i, p in enumerate(papers[:3], 1):
        text += f"\n论文{i}: {p.title}\n摘要: {(p.abstract or '')[:500]}\n"
    prompt = f"""对比以下{papers[:3]}篇论文，分析它们的异同点：

{text}

请输出：1) 共同主题 2) 方法差异 3) 主要发现对比"""
    return _call_llm(prompt)