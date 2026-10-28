"""
AI引擎自动查询模块
自动向 AI 发送品牌相关问题，解析回答中的引用情况、情感倾向、原文片段
"""
from __future__ import annotations
import os
import json
import re
import requests
from datetime import datetime
from dataclasses import dataclass, field, asdict

MONITOR_DB_PATH = os.path.join(os.path.dirname(__file__), "monitor_db.json")

DEFAULT_BRAND_KEYWORDS = ["标捷", "标捷智写", "标捷智审", "标捷AI标书", "标捷投标", "AI标书"]

# 可选模型（均通过 SiliconFlow 同一 API Key 调用）
MODELS = {
    "千问 Qwen2.5": "Qwen/Qwen2.5-7B-Instruct",
    "DeepSeek-V3":  "deepseek-ai/DeepSeek-V3",
    "GLM-4":        "THUDM/glm-4-9b-chat",
}


@dataclass
class QueryResult:
    query: str
    answer: str
    brand_mentioned: bool
    brand_keywords_found: list[str]
    sentiment: str          # positive / neutral / negative / not_mentioned
    citation_snippet: str   # AI回答中涉及你品牌的原文片段
    position: int           # 品牌在回答中出现的顺序（第几个被提到）
    queried_at: str = field(default_factory=lambda: datetime.now().isoformat())
    engine: str = "kimi"
    model_name: str = ""    # 显示名，如 "DeepSeek-V3"
    no_mention_reason: str = ""  # 未提及品牌时的原因分析
    citations: list[str] = field(default_factory=list)
    query_id: str = ""


@dataclass
class MonitorRun:
    id: str
    run_at: str
    brand_keywords: list[str]
    results: list[dict]     # list of QueryResult.to_dict()
    summary: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class MonitorDB:
    def __init__(self, path: str = MONITOR_DB_PATH):
        self.path = path
        self._data: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def save_run(self, run: MonitorRun):
        self._data.append(run.to_dict())
        self._save()

    def all_runs(self) -> list[dict]:
        return self._data

    def latest_run(self) -> dict | None:
        return self._data[-1] if self._data else None


def _call_llm(query: str, api_key: str, model_id: str = "Qwen/Qwen2.5-7B-Instruct") -> tuple[str, list[str]]:
    """调用 SiliconFlow API，返回 (answer_text, citations)"""
    resp = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": query}],
            "max_tokens": 512,
            "temperature": 0.3,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    answer = data["choices"][0]["message"]["content"]
    return answer, []


def _analyze_no_mention(
    query: str,
    answer: str,
    brand_keywords: list[str],
    competitor_keywords: list[str],
    api_key: str,
) -> str:
    """
    对未提及品牌的AI回答进行原因分析。
    返回 1-3 句中文结论，说明为什么品牌没被收录。
    """
    competitors_in_answer = [kw for kw in competitor_keywords if kw in answer]
    competitor_hint = f"（其中提到了竞品：{', '.join(competitors_in_answer)}）" if competitors_in_answer else ""

    meta_prompt = f"""你是一名GEO（生成式引擎优化）分析师。

用户问题：「{query}」

AI的回答如下：
「{answer}」

品牌关键词「{'、'.join(brand_keywords)}」在上述回答中均未出现{competitor_hint}。

请从以下角度简要分析该品牌未被AI提及的可能原因（1-3句，直接给结论，不要列编号）：
1. 竞品遮蔽：回答中是否提到了其他竞品，挤占了位置？
2. 关键词缺失：回答涉及哪些词/产品，与该品牌的内容差距在哪？
3. 主题偏差：该问题的语义是否与品牌主要内容方向匹配？
4. 训练数据不足：是否可能因为该品牌在网络上的内容量不足导致模型未知晓？

请用简洁中文回答，不超过80字。"""

    try:
        reason, _ = _call_llm(meta_prompt, api_key, model_id="Qwen/Qwen2.5-7B-Instruct")
        return reason.strip()
    except Exception:
        return "原因分析失败（API调用出错）"


def _parse_sentiment(answer: str, brand_keywords: list[str]) -> tuple[str, str, int]:
    """从AI回答中提取品牌情感、原文片段、出现位置"""
    found_keywords = [kw for kw in brand_keywords if kw in answer]
    if not found_keywords:
        return "not_mentioned", "", -1

    sentences = re.split(r'[。！？\n]', answer)
    snippet_sentences = [s.strip() for s in sentences if any(kw in s for kw in found_keywords)]
    snippet = "；".join(snippet_sentences[:2])

    positive_words = ["推荐", "好用", "优秀", "高效", "专业", "领先", "强大", "值得"]
    negative_words = ["不推荐", "较差", "问题", "缺点", "不稳定", "风险"]
    text_around = snippet.lower()
    pos_count = sum(1 for w in positive_words if w in text_around)
    neg_count = sum(1 for w in negative_words if w in text_around)

    if pos_count > neg_count:
        sentiment = "positive"
    elif neg_count > pos_count:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    position = next(
        (i + 1 for i, s in enumerate(sentences) if any(kw in s for kw in found_keywords)),
        -1
    )
    return sentiment, snippet, position


def run_monitor(
    brand_keywords: list[str] | None = None,
    api_key: str | None = None,
    queries: list[str] | None = None,
    selected_models: list[str] | None = None,
) -> MonitorRun:
    """
    执行一次完整的AI引擎监测。
    对每条提示词 × 每个选中模型各查询一次，返回 MonitorRun 结果。
    selected_models: MODELS 中的显示名列表，默认全选。
    """
    import uuid

    brand_keywords = brand_keywords or DEFAULT_BRAND_KEYWORDS
    queries = queries or []
    key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")

    # 确定要查询的模型列表
    if selected_models:
        active_models = {name: MODELS[name] for name in selected_models if name in MODELS}
    else:
        active_models = MODELS
    if not active_models:
        active_models = MODELS

    results = []
    # 用于统计：每条 query 是否至少有一个模型提及（去重计 mention_count）
    query_any_mentioned: dict[str, bool] = {q: False for q in queries}
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0, "not_mentioned": 0}
    per_model_stats: dict[str, dict] = {
        name: {"mention_count": 0, "total": 0, "mention_rate": 0.0}
        for name in active_models
    }

    # 所有竞品词 = brand_keywords 去掉"我方"也行，这里全传，让分析函数自己过滤
    competitor_kws = brand_keywords

    for query in queries:
        for model_name, model_id in active_models.items():
            try:
                answer, citations = _call_llm(query, key, model_id=model_id)
                found_kws = [kw for kw in brand_keywords if kw in answer]
                sentiment, snippet, position = _parse_sentiment(answer, brand_keywords)

                no_mention_reason = ""
                if not found_kws:
                    no_mention_reason = _analyze_no_mention(
                        query, answer, brand_keywords, competitor_kws, key
                    )

                qr = QueryResult(
                    query=query,
                    answer=answer,
                    brand_mentioned=bool(found_kws),
                    brand_keywords_found=found_kws,
                    sentiment=sentiment,
                    citation_snippet=snippet,
                    position=position,
                    engine=model_id,
                    model_name=model_name,
                    no_mention_reason=no_mention_reason,
                    citations=citations,
                )
                results.append(asdict(qr))

                per_model_stats[model_name]["total"] += 1
                if found_kws:
                    per_model_stats[model_name]["mention_count"] += 1
                    query_any_mentioned[query] = True
                sentiment_counts[sentiment] += 1

            except Exception as e:
                results.append({
                    "query": query, "answer": f"[ERROR] {e}",
                    "brand_mentioned": False, "brand_keywords_found": [],
                    "sentiment": "not_mentioned", "citation_snippet": "",
                    "position": -1, "engine": model_id,
                    "model_name": model_name, "no_mention_reason": "",
                    "citations": [], "query_id": "",
                    "queried_at": datetime.now().isoformat(),
                })
                per_model_stats[model_name]["total"] += 1
                sentiment_counts["not_mentioned"] += 1

    # 计算各模型提及率
    for name, s in per_model_stats.items():
        if s["total"] > 0:
            s["mention_rate"] = round(s["mention_count"] / s["total"] * 100, 1)

    mention_count = sum(1 for v in query_any_mentioned.values() if v)

    run = MonitorRun(
        id=str(uuid.uuid4()),
        run_at=datetime.now().isoformat(),
        brand_keywords=brand_keywords,
        results=results,
        summary={
            "total_queries": len(queries),
            "mention_count": mention_count,
            "mention_rate": round(mention_count / len(queries) * 100, 1) if queries else 0.0,
            "sentiment_counts": sentiment_counts,
            "per_model_stats": per_model_stats,
            "models_used": list(active_models.keys()),
        },
    )
    return run


def get_mention_rate_around_date(runs: list[dict], publish_date: str) -> tuple[float, float, str]:
    """
    给定内容发布日期，找出发布前最近一次和发布后最近一次监测的提及率。
    返回 (before_rate, after_rate, after_run_date)，无数据时返回 -1.0。
    """
    if not runs:
        return -1.0, -1.0, ""

    sorted_runs = sorted(runs, key=lambda r: r.get("run_at", ""))
    before_rate = -1.0
    after_rate = -1.0
    after_date = ""

    for run in sorted_runs:
        run_date = run.get("run_at", "")[:10]
        rate = run.get("summary", {}).get("mention_rate", -1.0)
        if run_date <= publish_date:
            before_rate = rate
        elif run_date > publish_date and after_rate < 0:
            after_rate = rate
            after_date = run_date

    return before_rate, after_rate, after_date
