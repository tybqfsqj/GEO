"""
GEO 贡献分析引擎
对每篇内容从多个维度评估其对 Generative Engine Optimization 的贡献
"""
from __future__ import annotations
import os
import re
import requests
from dataclasses import dataclass
from data_model import ContentItem

# AI大模型会被"喂"哪些平台的内容（影响GEO权重）
AI_FRIENDLY_PLATFORMS = {
    "知乎": 0.95,    # 问答结构、被大量爬取
    "CSDN": 0.90,    # 技术内容高度被引用
    "百家号": 0.70,
    "头条": 0.65,
    "公众号": 0.60,  # 需要外链才能被爬取
    "B站": 0.55,     # 视频字幕有一定权重
    "抖音": 0.25,    # 视频平台，文字权重低
    "视频号": 0.20,
}

# GEO友好的关键词特征（针对AI标书场景）
GEO_POWER_KEYWORDS = [
    "AI标书", "AI招投标", "AI写标书", "智能标书", "标书生成",
    "投标文件", "招标文件", "AI辅助", "自动生成标书",
    "标书制作", "投标方案", "评分标准", "技术标", "商务标",
]


@dataclass
class GEOScoreDetail:
    platform_weight: float       # 平台AI友好度
    keyword_coverage: float      # 核心关键词覆盖率
    content_structure: float     # 内容结构分（有无问答/列表/定义）
    engagement_signal: float     # 互动信号（点赞评论转发）
    citation_bonus: float        # 已被AI引用的加分
    monitor_signal: float        # AI监测提及率信号
    total: float

    def to_dict(self) -> dict:
        return {
            "平台AI友好度": round(self.platform_weight, 2),
            "关键词覆盖率": round(self.keyword_coverage, 2),
            "内容结构分": round(self.content_structure, 2),
            "互动信号分": round(self.engagement_signal, 2),
            "AI引用加分": round(self.citation_bonus, 2),
            "AI监测信号": round(self.monitor_signal, 2),
            "综合GEO评分": round(self.total, 2),
        }


def analyze_geo(item: ContentItem) -> GEOScoreDetail:
    """计算单篇内容的GEO贡献评分（0-100分）"""

    # 1. 平台权重
    platform_weight = AI_FRIENDLY_PLATFORMS.get(item.platform, 0.5) * 25

    # 2. 关键词覆盖率
    combined_text = (item.title + " " + item.summary + " " + " ".join(item.keywords)).lower()
    matched = sum(1 for kw in GEO_POWER_KEYWORDS if kw in combined_text)
    keyword_coverage = min(matched / max(len(GEO_POWER_KEYWORDS) * 0.3, 1), 1.0) * 20

    # 3. 内容结构分（软文 > 视频，有问答结构加分）
    structure_base = {"软文": 1.0, "问答": 1.0, "长视频": 0.6, "短视频": 0.3}.get(item.content_type, 0.5)
    # 标题含"如何""怎么""什么是"等问答型词语加分
    question_words = ["如何", "怎么", "什么是", "为什么", "哪些", "区别", "对比", "指南", "教程"]
    has_question = any(w in item.title for w in question_words)
    content_structure = structure_base * (1.15 if has_question else 1.0) * 20
    content_structure = min(content_structure, 20)

    # 4. 互动信号分（标准化到0-15）
    engagement_raw = item.views * 0.001 + item.likes * 0.1 + item.comments * 0.2 + item.shares * 0.3
    engagement_signal = min(engagement_raw / 100, 1.0) * 15

    # 5. AI引用加分（直接证据，权重最高）
    citation_bonus = min(item.ai_citation_count * 5, 20)

    # 6. AI监测信号（来自真实监测提及率，替代品牌词搜索）
    if item.monitor_mention_rate >= 0:
        monitor_signal = min(item.monitor_mention_rate / 100 * 10, 10)
    else:
        monitor_signal = 0.0

    total = platform_weight + keyword_coverage + content_structure + engagement_signal + citation_bonus + monitor_signal

    return GEOScoreDetail(
        platform_weight=platform_weight,
        keyword_coverage=keyword_coverage,
        content_structure=content_structure,
        engagement_signal=engagement_signal,
        citation_bonus=citation_bonus,
        monitor_signal=monitor_signal,
        total=round(min(total, 100), 1),
    )


def geo_advice(item: ContentItem, detail: GEOScoreDetail) -> list[str]:
    """根据评分明细给出具体改进建议"""
    tips = []

    if detail.keyword_coverage < 8:
        tips.append("关键词覆盖不足：标题或摘要中应包含'AI标书''智能标书'等核心词，提升被AI检索的概率")

    if detail.content_structure < 12 and item.content_type in ("短视频", "长视频"):
        tips.append("视频内容GEO权重天然较低，建议同步发布文字版本到知乎/CSDN，或在视频描述中补充完整文字稿")

    if detail.platform_weight < 12:
        tips.append(f"{item.platform}平台AI爬取权重较低，建议将同内容同步发布到知乎或CSDN以提升AI引用概率")

    if item.ai_citation_count == 0:
        tips.append("暂无AI引用记录：可手动在ChatGPT/Perplexity/文心等搜索品牌词，检查是否出现在回答中")

    if detail.engagement_signal < 5:
        tips.append("互动数据偏低，建议在评论区补充问答互动，问答结构内容更易被AI提取为参考源")

    if not any(w in item.title for w in ["如何", "怎么", "什么是", "指南", "对比"]):
        tips.append("标题建议改为问答型（如'如何用AI快速生成标书'），这类结构被AI引擎优先摘录")

    if detail.monitor_signal == 0 and item.monitor_mention_rate < 0:
        tips.append("暂无AI监测数据：在「AI引擎监测」页运行监测后，评分将更准确地反映真实AI可见度")
    elif detail.monitor_signal < 3 and item.monitor_mention_rate >= 0:
        tips.append(f"AI监测显示品牌提及率偏低（{item.monitor_mention_rate:.1f}%），建议参考下方AI深度分析获取针对性建议")

    return tips if tips else ["内容GEO表现良好，保持当前策略"]


def geo_advice_ai(item: ContentItem, detail: GEOScoreDetail,
                  latest_answers: list[str], api_key: str) -> list[str]:
    """把最近一次监测的AI回答发给大模型，分析为什么没提及该品牌并给出建议"""
    if not latest_answers or not api_key:
        return ["需要先运行AI引擎监测，并填写 SiliconFlow API Key"]

    answers_text = "\n---\n".join(latest_answers[:5])
    prompt = f"""我发布了一篇内容：《{item.title}》
平台：{item.platform}，类型：{item.content_type}
摘要：{item.summary or "（无摘要）"}
关键词：{", ".join(item.keywords) or "（无）"}

以下是AI对行业相关问题的实际回答，请分析：
1. 为什么AI没有提及我的品牌"标捷/AI标书"？
2. 这篇内容应该怎么改才能提升被AI引用的概率？
3. 给出3条具体可执行的改进建议（每条一行，以"-"开头）

AI回答内容：
{answers_text}"""

    try:
        resp = requests.post(
            "https://api.siliconflow.cn/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.5,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        return lines
    except Exception as e:
        return [f"AI分析请求失败：{e}"]


def batch_analyze(items: list[ContentItem]) -> list[tuple[ContentItem, GEOScoreDetail]]:
    results = []
    for item in items:
        detail = analyze_geo(item)
        item.geo_score = detail.total
        item.geo_score_detail = detail.to_dict()
        results.append((item, detail))
    return results
