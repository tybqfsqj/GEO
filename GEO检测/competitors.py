"""
竞品GEO对比追踪模块
在AI回答中统计你的品牌 vs 竞品的出现频率、情感、位置
"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from urllib.parse import urlparse

COMPETITOR_DB_PATH = os.path.join(os.path.dirname(__file__), "competitor_db.json")

# 默认竞品列表，可在仪表盘中修改
DEFAULT_COMPETITORS = ["投标宝", "中标王", "BidAI", "标书助手", "AI投标"]

SENTIMENT_LABEL = {
    "positive": "正面",
    "neutral": "中性",
    "negative": "负面",
    "not_mentioned": "未提及",
}

STAGE_LABELS = {
    "awareness":  "认知阶段 — 了解AI标书概念",
    "comparison": "比较阶段 — 选择哪个产品",
    "purchase":   "购买阶段 — 怎么用/怎么买",
}

DEFAULT_QUERY_TEMPLATES = {
    "awareness": [
        {"id": "a1", "text": "什么是AI标书？有哪些工具可以用？", "enabled": True},
        {"id": "a2", "text": "AI写标书靠谱吗？有哪些产品可以用？", "enabled": True},
    ],
    "comparison": [
        {"id": "c1", "text": "推荐几款好用的AI标书工具，分别有什么特点？", "enabled": True},
        {"id": "c2", "text": "智能标书生成软件哪个好用？", "enabled": True},
    ],
    "purchase": [
        {"id": "p1", "text": "投标文件可以用AI自动生成吗？有什么工具推荐？", "enabled": True},
        {"id": "p2", "text": "AI辅助招投标有哪些工具？怎么操作？", "enabled": True},
    ],
}


@dataclass
class BrandStats:
    brand: str
    mention_count: int = 0
    total_queries: int = 0
    avg_position: float = 0.0       # 平均出现在第几句（越小越好）
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    snippets: list[str] = field(default_factory=list)

    @property
    def mention_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return round(self.mention_count / self.total_queries * 100, 1)

    @property
    def sentiment_score(self) -> float:
        """正面率 - 负面率，-100到100"""
        total = self.positive_count + self.neutral_count + self.negative_count
        if total == 0:
            return 0.0
        return round((self.positive_count - self.negative_count) / total * 100, 1)

    def to_dict(self):
        return {
            **asdict(self),
            "mention_rate": self.mention_rate,
            "sentiment_score": self.sentiment_score,
        }


def build_competitor_stats(
    monitor_runs: list[dict],
    my_brand_keywords: list[str],
    competitors: list[str],
) -> dict[str, BrandStats]:
    """从历次监测记录中汇总各品牌的GEO表现"""
    all_brands = list(my_brand_keywords) + competitors
    stats: dict[str, BrandStats] = {b: BrandStats(brand=b) for b in all_brands}

    for run in monitor_runs:
        for result in run.get("results", []):
            answer = result.get("answer", "")
            sentiment = result.get("sentiment", "not_mentioned")
            position = result.get("position", -1)

            for brand in all_brands:
                s = stats[brand]
                s.total_queries += 1
                if brand in answer:
                    s.mention_count += 1
                    if position > 0:
                        # 滚动平均位置
                        if s.avg_position == 0:
                            s.avg_position = position
                        else:
                            s.avg_position = round(
                                (s.avg_position * (s.mention_count - 1) + position) / s.mention_count, 1
                            )
                    # 情感只统计含该品牌的句子
                    snippet = result.get("citation_snippet", "")
                    if brand in snippet or brand in answer:
                        if sentiment == "positive":
                            s.positive_count += 1
                        elif sentiment == "negative":
                            s.negative_count += 1
                        else:
                            s.neutral_count += 1
                        if snippet and snippet not in s.snippets:
                            s.snippets.append(snippet)

    return stats


class CompetitorDB:
    def __init__(self, path: str = COMPETITOR_DB_PATH):
        self.path = path
        self._data: dict = {"competitors": DEFAULT_COMPETITORS, "my_brand_keywords": ["标捷", "标捷智写", "标捷智审", "标捷AI标书", "标捷投标", "AI标书"]}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        # 迁移：旧数据没有 query_templates 字段时自动补充
        if "query_templates" not in self._data:
            self._data["query_templates"] = DEFAULT_QUERY_TEMPLATES
            self._save()

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get_competitors(self) -> list[str]:
        return self._data.get("competitors", DEFAULT_COMPETITORS)

    def set_competitors(self, competitors: list[str]):
        self._data["competitors"] = competitors
        self._save()

    def get_my_brands(self) -> list[str]:
        return self._data.get("my_brand_keywords", ["标捷", "AI标书"])

    def set_my_brands(self, brands: list[str]):
        self._data["my_brand_keywords"] = brands
        self._save()

    def get_query_templates(self) -> dict:
        return self._data.get("query_templates", DEFAULT_QUERY_TEMPLATES)

    def set_query_templates(self, templates: dict):
        self._data["query_templates"] = templates
        self._save()

    def get_all_enabled_queries(self) -> list[str]:
        result = []
        for stage_items in self.get_query_templates().values():
            for item in stage_items:
                if item.get("enabled", True):
                    result.append(item["text"])
        return result

    def add_query(self, stage: str, text: str) -> str:
        templates = self.get_query_templates()
        if stage not in templates:
            templates[stage] = []
        new_id = str(uuid.uuid4())[:8]
        templates[stage].append({"id": new_id, "text": text, "enabled": True})
        self.set_query_templates(templates)
        return new_id

    def remove_query(self, stage: str, query_id: str):
        templates = self.get_query_templates()
        if stage in templates:
            templates[stage] = [q for q in templates[stage] if q["id"] != query_id]
            self.set_query_templates(templates)

    def toggle_query(self, stage: str, query_id: str, enabled: bool):
        templates = self.get_query_templates()
        if stage in templates:
            for q in templates[stage]:
                if q["id"] == query_id:
                    q["enabled"] = enabled
                    break
            self.set_query_templates(templates)


def aggregate_citations(monitor_runs: list[dict], my_brand_keywords: list[str]) -> list[dict]:
    """从监测记录中提取引用来源，按域名聚合，仅统计品牌被提及时的引用"""
    domain_map: dict[str, dict] = {}

    for run in monitor_runs:
        run_at = run.get("run_at", "")
        for result in run.get("results", []):
            if not result.get("brand_mentioned", False):
                continue
            for url in result.get("citations", []):
                try:
                    netloc = urlparse(url).netloc.lstrip("www.")
                except Exception:
                    continue
                if not netloc:
                    continue
                if netloc not in domain_map:
                    domain_map[netloc] = {"domain": netloc, "count": 0, "urls": [], "last_seen": ""}
                domain_map[netloc]["count"] += 1
                if url not in domain_map[netloc]["urls"]:
                    domain_map[netloc]["urls"].append(url)
                if run_at > domain_map[netloc]["last_seen"]:
                    domain_map[netloc]["last_seen"] = run_at

    return sorted(domain_map.values(), key=lambda x: x["count"], reverse=True)
