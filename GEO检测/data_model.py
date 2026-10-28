"""
内容素材数据模型 - 支持多平台内容统一管理
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from enum import Enum

DB_PATH = os.path.join(os.path.dirname(__file__), "content_db.json")

class Platform(str, Enum):
    ZHIHU = "知乎"
    BAIJIAHAO = "百家号"
    CSDN = "CSDN"
    TOUTIAO = "头条"
    WECHAT = "公众号"
    DOUYIN = "抖音"
    SHIPINHAO = "视频号"
    BILIBILI = "B站"

class ContentType(str, Enum):
    ARTICLE = "软文/图文"
    QA = "问答"
    SHORT_VIDEO = "短视频"
    LONG_VIDEO = "长视频"
    WECHAT_ARTICLE = "公众号图文"
    WECHAT_MINI = "公众号短内容"
    WECHAT_VIDEO = "公众号视频号"
    DOUYIN_SHORT = "抖音短视频"
    DOUYIN_LIVE = "抖音直播"
    BILIBILI_VIDEO = "B站视频"
    BILIBILI_COLUMN = "B站专栏"

# 每个平台对应可选的内容类型
PLATFORM_CONTENT_TYPES: dict[str, list[str]] = {
    "知乎":  ["软文/图文", "问答", "短视频"],
    "CSDN":  ["软文/图文", "问答"],
    "百家号": ["软文/图文", "短视频", "长视频"],
    "头条":  ["软文/图文", "短视频", "长视频", "问答"],
    "公众号": ["公众号图文", "公众号短内容", "公众号视频号"],
    "抖音":  ["抖音短视频", "抖音直播"],
    "视频号": ["短视频", "长视频", "公众号视频号"],
    "B站":   ["B站视频", "B站专栏", "短视频"],
}

@dataclass
class ContentItem:
    id: str
    title: str
    platform: str
    content_type: str
    publish_date: str          # YYYY-MM-DD
    url: str
    keywords: list[str] = field(default_factory=list)
    summary: str = ""

    # 平台原生数据（手动录入或API抓取）
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    followers_gained: int = 0

    # GEO 专项指标（手动录入）
    ai_citation_count: int = 0          # AI引擎引用次数（手动查询后填入）
    ai_citation_sources: list[str] = field(default_factory=list)  # 哪些AI引用了

    # 品牌词搜索量变化（手动录入，发布前后对比）
    brand_search_before: int = 0
    brand_search_after: int = 0

    # 内容质量自评分（GEO分析引擎自动计算）
    geo_score: float = 0.0
    geo_score_detail: dict = field(default_factory=dict)

    # AI监测信号（由监测模块写入，-1表示无数据）
    monitor_mention_rate: float = -1.0

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ContentDB:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def save_item(self, item: ContentItem):
        item.updated_at = datetime.now().isoformat()
        self._data[item.id] = item.to_dict()
        self._save()

    def get_item(self, item_id: str) -> Optional[ContentItem]:
        d = self._data.get(item_id)
        return ContentItem.from_dict(d) if d else None

    def delete_item(self, item_id: str):
        self._data.pop(item_id, None)
        self._save()

    def all_items(self) -> list[ContentItem]:
        return [ContentItem.from_dict(d) for d in self._data.values()]

    def export_to_excel(self, path: str):
        import pandas as pd
        items = self.all_items()
        if not items:
            return
        rows = []
        for item in items:
            rows.append({
                "ID": item.id,
                "标题": item.title,
                "平台": item.platform,
                "类型": item.content_type,
                "发布日期": item.publish_date,
                "链接": item.url,
                "关键词": ", ".join(item.keywords),
                "摘要": item.summary,
                "阅读/播放量": item.views,
                "点赞": item.likes,
                "评论": item.comments,
                "转发/分享": item.shares,
                "新增粉丝": item.followers_gained,
                "AI引用次数": item.ai_citation_count,
                "AI引用来源": ", ".join(item.ai_citation_sources),
                "品牌词搜索量(发布前)": item.brand_search_before,
                "品牌词搜索量(发布后)": item.brand_search_after,
                "GEO评分": item.geo_score,
                "备注": item.notes,
            })
        pd.DataFrame(rows).to_excel(path, index=False)
