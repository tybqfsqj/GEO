"""
GEO 监控仪表盘 - 主入口
运行: streamlit run dashboard.py
"""
import os
import uuid
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from data_model import ContentDB, ContentItem, Platform, ContentType, PLATFORM_CONTENT_TYPES
from geo_engine import analyze_geo, geo_advice, geo_advice_ai, batch_analyze
from ai_monitor import MonitorDB, run_monitor, DEFAULT_BRAND_KEYWORDS, get_mention_rate_around_date, MODELS
from competitors import CompetitorDB, build_competitor_stats, SENTIMENT_LABEL, STAGE_LABELS, aggregate_citations


def compute_prompt_stats(runs):
    """Compute per-prompt mention rate from historical monitor runs."""
    stats = {}
    for run in runs:
        for result in run.get("results", []):
            q = result.get("query", "")
            if not q:
                continue
            if q not in stats:
                stats[q] = {"mention_count": 0, "total": 0}
            stats[q]["total"] += 1
            if result.get("brand_mentioned"):
                stats[q]["mention_count"] += 1
    for q in stats:
        t = stats[q]["total"]
        stats[q]["mention_rate"] = round(stats[q]["mention_count"] / t * 100, 1) if t > 0 else 0
    return stats


RECOMMENDED_PROMPTS = {
    "awareness": [
        "有哪些好用的AI标书生成工具？",
        "AI辅助投标有哪些主流产品？",
        "智能投标软件推荐有哪些？",
        "用AI写标书靠谱吗？有哪些平台可以试试？",
        "标书制作有什么AI工具可以推荐？",
        "现在有哪些AI工具能帮助快速生成投标文件？",
        "做投标的公司都在用什么软件提高效率？",
    ],
    "comparison": [
        "AI标书工具哪家效果最好，怎么对比？",
        "投标宝和标捷哪个更好用？",
        "AI投标工具的价格和功能怎么比较？",
        "生成标书的AI工具，哪个最准确最专业？",
        "市面上AI标书工具的优缺点对比",
        "标捷AI标书和其他标书工具比，有什么优势？",
    ],
    "purchase": [
        "标捷AI标书怎么注册使用？",
        "如何用AI快速生成一份完整的投标文件？",
        "AI标书工具的收费方式是怎样的？",
        "投标文件生成AI有没有免费试用？",
        "用AI标书工具能节省多少时间？",
    ],
}

st.set_page_config(page_title="GEO 内容监控", layout="wide", page_icon="📊")

# ── 品牌 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #F8FAFC; }
  [data-testid="stSidebar"] { background: #1E2A3A; }
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span { color: #C8D8EC !important; }
  .geo-header {
    background: linear-gradient(135deg, #1565C0 0%, #0D47A1 100%);
    padding: 20px 28px; border-radius: 12px; margin-bottom: 20px; color: white;
    display: flex; align-items: center; gap: 16px;
  }
  .geo-header-icon { font-size: 2rem; }
  .geo-header h2 { color: white !important; margin: 0; font-size: 1.5rem; }
  .geo-header p  { color: rgba(255,255,255,0.75) !important; margin: 4px 0 0; font-size: 0.88rem; }
  .empty-state {
    text-align: center; padding: 52px 24px; background: white;
    border-radius: 12px; border: 2px dashed #CBD5E0; margin: 16px 0;
  }
  .empty-state h3 { color: #4A5568; margin-bottom: 8px; }
  .empty-state p  { color: #718096; margin-bottom: 16px; }
  div[data-testid="metric-container"] {
    background: white; border-radius: 10px; padding: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }
</style>
""", unsafe_allow_html=True)

db           = ContentDB()
monitor_db   = MonitorDB()
competitor_db = CompetitorDB()

# ── 启动时从 .env 加载 API Key ────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)
except ImportError:
    pass

# ── Sidebar: API Key 统一管理 ──────────────────────────────
with st.sidebar:
    st.markdown("### 标捷 GEO监控")
    st.markdown("---")

    _env_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if _env_key:
        # Key 已由服务器配置，前端完全隐藏，直接写入 session
        st.session_state["siliconflow_key"] = _env_key
        st.success("AI 功能已就绪", icon="✅")
    else:
        # 本地开发模式：允许手动输入
        st.markdown("**SiliconFlow API Key**")
        _saved_key = st.session_state.get("siliconflow_key", "")
        sidebar_key = st.text_input(
            "API Key", type="password", value=_saved_key,
            help="从 siliconflow.cn 注册，注册即有免费额度",
            label_visibility="collapsed",
        )
        if sidebar_key:
            st.session_state["siliconflow_key"] = sidebar_key
            os.environ["SILICONFLOW_API_KEY"] = sidebar_key
            st.success("API Key 已就绪", icon="✅")
        else:
            st.warning("填写后可启用 AI 功能", icon="⚠️")

    st.markdown("---")
    _my_brands = competitor_db.get_my_brands()
    st.caption(f"监测品牌：{', '.join(_my_brands)}")
    _runs = monitor_db.all_runs()
    if _runs:
        _last = _runs[-1]
        st.caption(f"最近监测：{_last['run_at'][:10]}")
        st.caption(f"提及率：{_last['summary'].get('mention_rate', 0)}%")
    else:
        st.caption("尚无监测记录")

# ── 顶部标题 ─────────────────────────────────────────────────
st.markdown("""
<div class="geo-header">
  <div class="geo-header-icon">📊</div>
  <div>
    <h2>AI标书 · GEO内容监控</h2>
    <p>追踪推广素材在生成式AI引擎中的曝光与引用表现</p>
  </div>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["📋 内容管理", "📊 监测分析", "💬 提示词管理", "⚙️ 设置"])


# ══════════════════════════════════════════════════════════
# TAB 1 · 内容管理（原 Tab1 + Tab2）
# ══════════════════════════════════════════════════════════
with tabs[0]:
    mgmt_tabs = st.tabs(["已录入内容", "录入 / 更新素材"])

    # ── 已录入内容 ──────────────────────────────────────────
    with mgmt_tabs[0]:
        items = db.all_items()
        if not items:
            st.markdown("""
            <div class="empty-state">
              <h3>📄 还没有内容</h3>
              <p>在「录入 / 更新素材」标签页添加第一篇推广内容，<br>系统将自动计算 GEO 评分。</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            results = batch_analyze(items)
            for item, _ in results:
                db.save_item(item)

            rows = []
            for item, detail in results:
                rows.append({
                    "标题": item.title,
                    "平台": item.platform,
                    "类型": item.content_type,
                    "发布日期": item.publish_date,
                    "阅读/播放量": item.views,
                    "点赞": item.likes,
                    "评论": item.comments,
                    "转发": item.shares,
                    "AI引用次数": item.ai_citation_count,
                    "GEO评分": item.geo_score,
                    "链接": item.url,
                })

            df = pd.DataFrame(rows)

            # 平台筛选
            all_platforms = sorted(df["平台"].unique().tolist())
            selected_platforms = st.multiselect(
                "按平台筛选", all_platforms, default=all_platforms, key="platform_filter"
            )
            df_show = df[df["平台"].isin(selected_platforms)] if selected_platforms else df

            st.dataframe(
                df_show.style.background_gradient(subset=["GEO评分"], cmap="RdYlGn"),
                use_container_width=True,
                hide_index=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 导出 Excel"):
                    path = "GEO内容报告.xlsx"
                    db.export_to_excel(path)
                    st.success(f"已导出到 {path}")
            with col2:
                del_id = st.text_input("输入 ID 前8位以删除内容", key="del_input")
                if del_id:
                    matched = [i for i in items if i.id.startswith(del_id)]
                    if matched:
                        target = matched[0]
                        st.warning(
                            f"将删除：**{target.title}** ({target.platform})  \n"
                            "此操作不可撤销，请确认。"
                        )
                        if st.button("确认删除", type="primary", key="confirm_del"):
                            db.delete_item(target.id)
                            st.success("已删除")
                            st.rerun()
                    else:
                        st.error("未找到匹配的内容 ID")

    # ── 录入 / 更新素材 ─────────────────────────────────────
    with mgmt_tabs[1]:
        st.subheader("录入新素材")
        st.caption("每次发布软文或视频后，在此录入基础信息；数据指标可后续补充更新")

        with st.form("add_content"):
            c1, c2, c3 = st.columns(3)
            with c1:
                title    = st.text_input("标题 *", placeholder="完整标题")
                platform = st.selectbox("平台 *", [p.value for p in Platform])
                # 根据平台动态限定内容类型选项
                type_options = PLATFORM_CONTENT_TYPES.get(platform, [t.value for t in ContentType])
                content_type = st.selectbox("内容类型 *", type_options)
            with c2:
                publish_date = st.date_input("发布日期 *", value=datetime.today())
                url          = st.text_input("链接 *", placeholder="https://...")
                keywords     = st.text_input("关键词（逗号分隔）", placeholder="AI标书, 智能投标")
            with c3:
                summary = st.text_area("摘要/正文简述", height=120)
                notes   = st.text_input("备注")

            st.markdown("**平台数据指标**（发布后填写）")
            m1, m2, m3, m4, m5 = st.columns(5)
            views     = m1.number_input("阅读/播放量", min_value=0, value=0)
            likes     = m2.number_input("点赞",        min_value=0, value=0)
            comments  = m3.number_input("评论",        min_value=0, value=0)
            shares    = m4.number_input("转发/分享",   min_value=0, value=0)
            followers = m5.number_input("新增粉丝",    min_value=0, value=0)

            st.markdown("**GEO专项数据**")
            g1, g2   = st.columns(2)
            ai_citations = g1.number_input(
                "AI引用次数", min_value=0, value=0,
                help="在 ChatGPT/Perplexity/文心等搜索品牌词后，出现引用则 +1",
            )
            ai_sources = g2.text_input("被哪些AI引用", placeholder="ChatGPT, Perplexity")

            submitted = st.form_submit_button("✅ 保存")
            if submitted:
                if not title or not url:
                    st.error("标题和链接为必填项")
                else:
                    item = ContentItem(
                        id=str(uuid.uuid4()),
                        title=title, platform=platform, content_type=content_type,
                        publish_date=str(publish_date), url=url,
                        keywords=[k.strip() for k in keywords.split(",") if k.strip()],
                        summary=summary, notes=notes,
                        views=views, likes=likes, comments=comments,
                        shares=shares, followers_gained=followers,
                        ai_citation_count=ai_citations,
                        ai_citation_sources=[s.strip() for s in ai_sources.split(",") if s.strip()],
                    )
                    detail = analyze_geo(item)
                    item.geo_score        = detail.total
                    item.geo_score_detail = detail.to_dict()
                    db.save_item(item)
                    st.success(f"已保存！GEO评分：{detail.total}/100")
                    st.rerun()


# ══════════════════════════════════════════════════════════
# TAB 2 · 监测分析（原 Tab3+4+5+6+7）
# ══════════════════════════════════════════════════════════
with tabs[1]:
    analysis_tabs = st.tabs(["📈 数据仪表盘", "🔍 GEO分析", "💡 改进建议", "🤖 AI引擎监测", "⚔️ 竞品对比"])

    # ── 数据仪表盘 ──────────────────────────────────────────
    with analysis_tabs[0]:
        items = db.all_items()
        if not items:
            st.markdown("""
            <div class="empty-state">
              <h3>📈 暂无数据</h3>
              <p>在「内容管理」录入内容后，这里将自动展示全局数据概览与趋势图表。</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            results = batch_analyze(items)
            df_rows = []
            for item, detail in results:
                df_rows.append({
                    "标题": item.title, "平台": item.platform, "类型": item.content_type,
                    "发布日期": item.publish_date, "阅读量": item.views,
                    "点赞": item.likes, "评论": item.comments, "转发": item.shares,
                    "AI引用": item.ai_citation_count, "GEO评分": item.geo_score,
                    "AI监测提及率%": item.monitor_mention_rate if item.monitor_mention_rate >= 0 else 0,
                })
            df = pd.DataFrame(df_rows)

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("内容总数",    len(items))
            k2.metric("总阅读/播放量", f"{df['阅读量'].sum():,}")
            k3.metric("AI引用总次数", int(df['AI引用'].sum()))
            k4.metric("平均GEO评分", f"{df['GEO评分'].mean():.1f}")
            k5.metric("最高GEO评分", f"{df['GEO评分'].max():.1f}")

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                fig1 = px.bar(
                    df.sort_values("GEO评分", ascending=False),
                    x="标题", y="GEO评分", color="平台",
                    title="各内容GEO评分排名",
                )
                fig1.update_xaxes(tickangle=45)
                st.plotly_chart(fig1, use_container_width=True)
            with col2:
                platform_df = df.groupby("平台").agg(
                    内容数=("标题", "count"),
                    平均GEO评分=("GEO评分", "mean"),
                    总阅读量=("阅读量", "sum"),
                    总AI引用=("AI引用", "sum"),
                ).reset_index()
                fig2 = px.scatter(
                    platform_df, x="总阅读量", y="平均GEO评分",
                    size="内容数", color="平台", text="平台",
                    title="平台效果矩阵（气泡大小=内容数量）",
                )
                st.plotly_chart(fig2, use_container_width=True)

            df["发布日期"] = pd.to_datetime(df["发布日期"])
            df_sorted = df.sort_values("发布日期")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=df_sorted["发布日期"], y=df_sorted["GEO评分"],
                mode="lines+markers", name="GEO评分", yaxis="y1",
            ))
            fig3.add_trace(go.Bar(
                x=df_sorted["发布日期"], y=df_sorted["阅读量"],
                name="阅读量", yaxis="y2", opacity=0.4,
            ))
            fig3.update_layout(
                title="发布时间线：GEO评分 vs 阅读量",
                yaxis=dict(title="GEO评分"),
                yaxis2=dict(title="阅读量", overlaying="y", side="right"),
            )
            st.plotly_chart(fig3, use_container_width=True)

            st.markdown("---")
            st.subheader("内容发布 vs AI提及率趋势")
            st.caption("发布内容（柱）和AI监测提及率（线）叠加，直观看出哪次发布推动了AI可见度提升")
            runs = monitor_db.all_runs()
            if not runs:
                st.info("运行「AI引擎监测」后，此图将显示内容发布与AI提及率的关联关系")
            else:
                monitor_df = pd.DataFrame([
                    {"日期": r["run_at"][:10], "AI提及率%": r["summary"].get("mention_rate", 0)}
                    for r in runs
                ])
                publish_df = df_sorted.groupby(df_sorted["发布日期"].dt.strftime("%Y-%m-%d")).agg(
                    发布数量=("标题", "count"),
                    内容列表=("标题", lambda x: "<br>".join(x.tolist())),
                ).reset_index().rename(columns={"发布日期": "日期"})

                fig_combined = go.Figure()
                fig_combined.add_trace(go.Bar(
                    x=publish_df["日期"], y=publish_df["发布数量"],
                    name="发布内容数", yaxis="y2", opacity=0.5,
                    marker_color="#90CAF9",
                    hovertext=publish_df["内容列表"],
                    hovertemplate="<b>%{x}</b><br>发布%{y}篇<br>%{hovertext}<extra></extra>",
                ))
                fig_combined.add_trace(go.Scatter(
                    x=monitor_df["日期"], y=monitor_df["AI提及率%"],
                    mode="lines+markers+text", name="AI提及率%",
                    text=monitor_df["AI提及率%"].astype(str) + "%",
                    textposition="top center",
                    line=dict(color="#F44336", width=2),
                    marker=dict(size=8),
                ))
                fig_combined.update_layout(
                    title="内容发布时间线 × AI提及率趋势",
                    yaxis=dict(title="AI提及率%", range=[0, 110]),
                    yaxis2=dict(title="发布内容数", overlaying="y", side="right", range=[0, 10]),
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_combined, use_container_width=True)

            cited = [
                (item.title, item.platform, item.ai_citation_count, ", ".join(item.ai_citation_sources))
                for item in items if item.ai_citation_count > 0
            ]
            if cited:
                st.markdown("### 已被AI引用的内容")
                st.dataframe(
                    pd.DataFrame(cited, columns=["标题", "平台", "引用次数", "引用来源"]),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("目前没有AI引用记录。参考「改进建议」标签页了解如何提升AI引用率。")

    # ── GEO 分析 ────────────────────────────────────────────
    with analysis_tabs[1]:
        items = db.all_items()
        if not items:
            st.markdown("""
            <div class="empty-state">
              <h3>🔍 暂无内容可分析</h3>
              <p>在「内容管理」录入内容后，可在此查看每篇内容的GEO得分详情与归因分析。</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            options  = {f"{i.title[:40]} ({i.platform})": i.id for i in items}
            sel_label = st.selectbox("选择内容", list(options.keys()))
            sel_item  = db.get_item(options[sel_label])
            detail    = analyze_geo(sel_item)

            # 计算与全库平均分的 delta
            all_scores = [i.geo_score for i in items if i.geo_score > 0]
            avg_score  = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
            delta_avg  = round(detail.total - avg_score, 1)

            col_score, col_avg = st.columns(2)
            col_score.metric(
                "GEO综合评分",
                f"{detail.total} / 100",
                delta=f"{delta_avg:+.1f} 较库内平均",
                delta_color="normal",
            )
            col_avg.metric("库内平均GEO评分", f"{avg_score} / 100")

            score_df = pd.DataFrame([
                {"维度": k, "得分": v}
                for k, v in detail.to_dict().items()
                if k != "综合GEO评分"
            ])
            fig = px.bar(
                score_df, x="维度", y="得分",
                color="得分", color_continuous_scale="RdYlGn",
                range_y=[0, 25], title="GEO各维度得分分布",
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("ℹ️ 评分依据说明（点击展开）"):
                st.markdown("""
**规则估算分（依据GEO行业研究经验，非实测数据）**
- **平台AI友好度**（满分25）：根据各平台被AI爬取/训练的公开研究结论，固定权重系数，不随你的内容变化
- **关键词覆盖率**（满分20）：统计标题+摘要中出现的行业核心词数量，是词频计算，不反映实际AI检索结果
- **内容结构分**（满分20）：根据内容类型（软文>视频）和标题是否含问答词判断，是规则打分
- **互动信号分**（满分15）：用你填写的阅读/点赞/评论/转发数按公式加权，数据来自你的手动录入

**真实数据分（来自实际AI引擎监测）**
- **AI引用加分**（满分20）：你手动记录的"AI引用次数"，每次+5分，是你亲自验证的真实数据
- **AI监测信号**（满分10）：运行「AI引擎监测」后，系统向AI发问并检测品牌是否被提及，是真实的AI回答数据

> 总结：前4项是基于行业规律的参考估算，可帮助判断优化方向；后2项是真实监测数据，更能反映实际AI可见度。建议定期运行AI监测，让评分更有依据。
""")

            st.markdown("**各维度说明**")
            c1, c2 = st.columns(2)
            with c1:
                st.metric("平台AI友好度",  f"{detail.platform_weight:.1f}/25",
                          help="平台内容被AI训练集和爬虫覆盖的概率，知乎/CSDN最高")
                st.metric("关键词覆盖率",  f"{detail.keyword_coverage:.1f}/20",
                          help="标题+摘要中包含AI标书核心关键词的数量")
                st.metric("内容结构分",    f"{detail.content_structure:.1f}/20",
                          help="软文/问答结构比视频更易被AI提取，问答型标题额外加分")
            with c2:
                st.metric("互动信号分",    f"{detail.engagement_signal:.1f}/15",
                          help="点赞/评论/转发综合加权，高互动=高权威性信号")
                st.metric("AI引用加分",    f"{detail.citation_bonus:.1f}/20",
                          help="直接被ChatGPT/Perplexity等引用，每次+5分，上限20")
                monitor_label = (
                    f"{sel_item.monitor_mention_rate:.1f}%"
                    if sel_item.monitor_mention_rate >= 0 else "暂无数据"
                )
                st.metric("AI监测信号", f"{detail.monitor_signal:.1f}/10",
                          help=f"最近一次AI监测提及率：{monitor_label}")

            st.markdown("---")
            st.subheader("📊 发布归因分析")
            runs = monitor_db.all_runs()
            before_rate, after_rate, after_date = get_mention_rate_around_date(
                runs, sel_item.publish_date
            )
            if before_rate < 0 and after_rate < 0:
                st.info("还没有覆盖该内容发布时间的监测记录，在「AI引擎监测」页运行监测后自动填充。")
            else:
                a1, a2, a3 = st.columns(3)
                a1.metric("发布前提及率", f"{before_rate:.1f}%" if before_rate >= 0 else "无数据")
                delta = round(after_rate - before_rate, 1) if before_rate >= 0 and after_rate >= 0 else None
                a2.metric(
                    "发布后提及率",
                    f"{after_rate:.1f}%" if after_rate >= 0 else "无数据",
                    delta=f"{delta:+.1f}%" if delta is not None else None,
                )
                a3.metric("归因监测日期", after_date or "—")
                if delta is not None:
                    if delta > 0:
                        st.success(f"发布这篇内容后，AI提及率提升了 {delta:.1f}%")
                    elif delta < 0:
                        st.warning(f"发布这篇内容后，AI提及率下降了 {abs(delta):.1f}%（可能受其他因素影响）")
                    else:
                        st.info("发布前后AI提及率无明显变化")

            st.markdown("---")
            st.markdown("**规则建议**")
            for tip in geo_advice(sel_item, detail):
                st.warning(f"💡 {tip}")

            st.markdown("---")
            st.subheader("✨ AI深度分析建议")
            _kimi = st.session_state.get("siliconflow_key", "")
            if not _kimi:
                st.info("在左侧边栏填写 SiliconFlow API Key 后可获取AI深度建议")
            elif st.button("获取AI深度分析", key="tab_geo_ai_advice"):
                runs = monitor_db.all_runs()
                if not runs:
                    st.error("请先在「AI引擎监测」页运行至少一次监测")
                else:
                    latest_answers = [
                        r.get("answer", "") for r in monitor_db.latest_run().get("results", [])
                        if not r.get("answer", "").startswith("[ERROR]")
                    ]
                    with st.spinner("AI正在分析，约需10秒..."):
                        ai_tips = geo_advice_ai(sel_item, detail, latest_answers, _kimi)
                    for tip in ai_tips:
                        if tip.strip():
                            st.info(tip)

    # ── 改进建议 ────────────────────────────────────────────
    with analysis_tabs[2]:
        st.subheader("全局改进建议 & GEO观测清单")
        items = db.all_items()

        st.markdown("### 📋 你还需要收集哪些数据才能完整观测GEO？")
        checklist = {
            "AI引用监测":   "每周手动在 ChatGPT / Perplexity / 文心一言 / DeepSeek 搜索「AI标书」「智能投标」，记录是否出现你的内容",
            "百度指数品牌词": "登录 index.baidu.com，追踪「标捷」「AI标书」等品牌词的每周搜索指数，记录发布前后变化",
            "搜索排名追踪":  "使用 5118.com 或爱站工具，追踪核心关键词在百度的自然排名变化",
            "反链增长":     "用站长工具检查你的网站新增了多少外部链接（平台内容发布会产生反链）",
            "官网流量来源":  "在 Google Analytics 或百度统计里，观察「直接流量」和「搜索来源」在每次发布后的变化",
            "问答平台收录":  "在知乎、百度知道搜索你的核心词，看有多少是你发布的内容被展示",
        }
        for item_name, desc in checklist.items():
            with st.expander(f"✅ {item_name}"):
                st.write(desc)

        if not items:
            st.markdown("""
            <div class="empty-state">
              <h3>💡 录入内容后查看具体建议</h3>
              <p>在「内容管理」添加内容后，这里将针对每篇内容给出优先级排序的改进建议。</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("---")
            st.markdown("### 💡 各内容改进建议")
            _kimi = st.session_state.get("siliconflow_key", "")
            if not _kimi:
                st.info("在左侧边栏填写 SiliconFlow API Key 后，可对每篇内容获取基于真实AI回答的深度建议")

            results       = batch_analyze(items)
            results_sorted = sorted(results, key=lambda x: x[1].total)
            latest_run    = monitor_db.latest_run()

            for item, detail in results_sorted:
                tips  = geo_advice(item, detail)
                color = "🔴" if detail.total < 30 else ("🟡" if detail.total < 60 else "🟢")
                with st.expander(f"{color} [{detail.total}/100] {item.title} ({item.platform})"):
                    for tip in tips:
                        st.write(f"• {tip}")
                    if _kimi and latest_run:
                        if st.button("✨ AI深度分析", key=f"ai_advice_{item.id}"):
                            latest_answers = [
                                r.get("answer", "") for r in latest_run.get("results", [])
                                if not r.get("answer", "").startswith("[ERROR]")
                            ]
                            with st.spinner("AI正在分析..."):
                                ai_tips = geo_advice_ai(item, detail, latest_answers, _kimi)
                            for t in ai_tips:
                                if t.strip():
                                    st.info(t)

    # ── AI引擎监测 ──────────────────────────────────────────
    with analysis_tabs[3]:
        st.subheader("AI引擎品牌监测")
        st.caption("自动向AI提问，检测你的品牌是否出现在回答中，以及AI如何描述你")

        _kimi        = st.session_state.get("siliconflow_key", "")
        my_brands    = competitor_db.get_my_brands()
        competitors  = competitor_db.get_competitors()
        all_keywords = my_brands + competitors

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**监测关键词**")
            st.write(", ".join(all_keywords))
        with col2:
            st.markdown("**查询模板数量**")
            st.write(f"{len(competitor_db.get_all_enabled_queries())} 条")

        if not _kimi:
            st.warning("请先在左侧边栏填写 SiliconFlow API Key 再运行监测")
        else:
            selected_model_names = st.multiselect(
                "选择查询模型（同一问题将同时发给所有选中模型）",
                list(MODELS.keys()),
                default=list(MODELS.keys()),
                key="monitor_models",
            )
            n_queries = len(competitor_db.get_all_enabled_queries())
            n_models  = len(selected_model_names) if selected_model_names else len(MODELS)
            st.caption(f"预计发送 {n_queries} 条提示词 × {n_models} 个模型 = {n_queries * n_models} 次API调用")

            if st.button("立即运行监测", type="primary"):
                with st.spinner(f"正在向 {n_models} 个模型发送查询，约需 {n_queries * n_models * 5} 秒..."):
                    queries = competitor_db.get_all_enabled_queries()
                    if not queries:
                        st.error("没有启用的查询模板，请在「提示词管理」中添加")
                    else:
                        run = run_monitor(
                            brand_keywords=all_keywords,
                            api_key=_kimi,
                            queries=queries,
                            selected_models=selected_model_names or None,
                        )
                        monitor_db.save_run(run)
                        st.success(f"监测完成！品牌提及率：{run.summary['mention_rate']}%")
                        st.rerun()

        runs = monitor_db.all_runs()
        if not runs:
            st.markdown("""
            <div class="empty-state">
              <h3>🤖 还没有监测记录</h3>
              <p>点击上方「立即运行监测」按钮，系统将自动向AI发送预设问题并记录品牌提及情况。</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            latest  = runs[-1]
            summary = latest.get("summary", {})
            models_used = summary.get("models_used", [])
            st.markdown(f"### 最新监测结果（{latest['run_at'][:10]}）")

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("提示词数",     summary.get("total_queries", 0))
            k2.metric("至少一模型提及", summary.get("mention_count", 0))
            k3.metric("综合提及率",   f"{summary.get('mention_rate', 0)}%")
            sc = summary.get("sentiment_counts", {})
            k4.metric("正面回答",     sc.get("positive", 0))

            # ── 各模型提及率横排 ──────────────────────────────
            per_model = summary.get("per_model_stats", {})
            if per_model:
                st.markdown("**各模型品牌提及率**")
                mcols = st.columns(len(per_model))
                for mi, (mname, mstat) in enumerate(per_model.items()):
                    mcols[mi].metric(
                        mname,
                        f"{mstat.get('mention_rate', 0)}%",
                        help=f"提及 {mstat.get('mention_count',0)}/{mstat.get('total',0)} 次",
                    )

            # ── 查询 × 模型矩阵表 ─────────────────────────────
            st.markdown("---")
            st.subheader("📊 收录矩阵")
            latest_results = latest.get("results", [])
            # 收集所有 (query, model_name) 组合
            matrix_data: dict[str, dict[str, str]] = {}
            for r in latest_results:
                q  = r.get("query", "")
                mn = r.get("model_name") or r.get("engine", "未知")
                if q not in matrix_data:
                    matrix_data[q] = {}
                matrix_data[q][mn] = "✅" if r.get("brand_mentioned") else "❌"

            if matrix_data:
                all_model_cols = models_used if models_used else sorted(
                    {r.get("model_name") or r.get("engine", "未知") for r in latest_results}
                )
                matrix_rows = []
                for q, model_map in matrix_data.items():
                    row = {"提示词": q[:45] + ("…" if len(q) > 45 else "")}
                    for mn in all_model_cols:
                        row[mn] = model_map.get(mn, "—")
                    matrix_rows.append(row)
                matrix_df = pd.DataFrame(matrix_rows)
                st.dataframe(matrix_df, use_container_width=True, hide_index=True)

            # ── 各条查询详情（按 query 分组，每模型一列）────────
            st.markdown("---")
            st.markdown("**各条查询详情**")

            # 按 query 分组
            from collections import defaultdict
            results_by_query: dict[str, list[dict]] = defaultdict(list)
            for r in latest_results:
                results_by_query[r.get("query", "")].append(r)

            for query_text, qresults in results_by_query.items():
                any_mentioned = any(r.get("brand_mentioned") for r in qresults)
                # expander 标题：每模型一个图标
                model_icons = "　".join(
                    f"{r.get('model_name') or r.get('engine','?')} {'✅' if r.get('brand_mentioned') else '❌'}"
                    for r in qresults
                )
                exp_color = "green" if any_mentioned else "red"
                exp_label = f":{exp_color}[{'✅ 至少一模型提及' if any_mentioned else '❌ 全部未提及'}]"
                with st.expander(f"{exp_label}　{query_text[:50]}　{model_icons}"):
                    cols = st.columns(len(qresults)) if len(qresults) > 1 else [st]
                    for ci, r in enumerate(qresults):
                        col = cols[ci] if len(qresults) > 1 else st
                        mname = r.get("model_name") or r.get("engine", "未知")
                        mentioned = r.get("brand_mentioned", False)
                        col.markdown(
                            f"<div style='background:{'#E8F5E9' if mentioned else '#FFF3E0'};"
                            f"border-radius:6px;padding:8px 10px;margin-bottom:6px'>"
                            f"<b>{mname}</b>　{'✅ 已提及' if mentioned else '❌ 未提及'}</div>",
                            unsafe_allow_html=True,
                        )
                        if r.get("citation_snippet"):
                            col.markdown(f"**片段：** {r['citation_snippet']}")
                            col.caption(
                                f"情感：{SENTIMENT_LABEL.get(r['sentiment'], r['sentiment'])}　"
                                f"位置：第 {r['position']} 句"
                            )
                        if not mentioned and r.get("no_mention_reason"):
                            col.warning(f"💡 未收录原因：{r['no_mention_reason']}")
                        with col.expander("查看完整回答"):
                            answer    = r.get("answer", "")
                            found_kws = r.get("brand_keywords_found", [])
                            highlighted = answer
                            for kw in found_kws:
                                highlighted = highlighted.replace(
                                    kw,
                                    f'<mark style="background:#FFF176;padding:0 2px;'
                                    f'border-radius:3px;font-weight:600">{kw}</mark>',
                                )
                            if found_kws:
                                col.markdown(highlighted, unsafe_allow_html=True)
                            else:
                                col.write(answer)

            if len(runs) > 1:
                st.markdown("---")
                st.markdown("**历次监测提及率趋势**")
                trend_df = pd.DataFrame([
                    {"日期": r["run_at"][:10], "提及率%": r["summary"].get("mention_rate", 0)}
                    for r in runs
                ])
                st.line_chart(trend_df.set_index("日期"))

                with st.expander("按提示词查看提及趋势"):
                    for query_text in competitor_db.get_all_enabled_queries():
                        query_runs = []
                        for r in runs:
                            for res in r.get("results", []):
                                if res.get("query") == query_text:
                                    query_runs.append({
                                        "日期": r["run_at"][:10],
                                        "提及": 1 if res.get("brand_mentioned") else 0,
                                    })
                        if not query_runs:
                            continue
                        total    = len(query_runs)
                        mentioned_count = sum(x["提及"] for x in query_runs)
                        rate     = round(mentioned_count / total * 100, 1)
                        label    = (
                            f"{'🟢' if rate >= 50 else '🔴'} "
                            f"{query_text[:40]}... — 提及率 {rate}% ({mentioned_count}/{total}次)"
                        )
                        with st.expander(label):
                            q_df = pd.DataFrame(query_runs)
                            st.bar_chart(q_df.set_index("日期")["提及"])

    # ── 竞品对比 ────────────────────────────────────────────
    with analysis_tabs[4]:
        st.subheader("竞品GEO对比")
        st.caption("在AI回答中，你的品牌 vs 竞品的出现频率、情感、位置对比")

        runs = monitor_db.all_runs()
        if not runs:
            st.markdown("""
            <div class="empty-state">
              <h3>⚔️ 暂无竞品数据</h3>
              <p>先在「AI引擎监测」运行至少一次监测，系统将自动统计各品牌在AI回答中的表现。</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            my_brands   = competitor_db.get_my_brands()
            competitors = competitor_db.get_competitors()
            stats       = build_competitor_stats(runs, my_brands, competitors)

            rows = []
            for brand, s in stats.items():
                rows.append({
                    "品牌": brand,
                    "是否我方": "我方" if brand in my_brands else "竞品",
                    "提及率%": s.mention_rate,
                    "提及次数": s.mention_count,
                    "平均出现位置": s.avg_position,
                    "情感得分": s.sentiment_score,
                    "正面": s.positive_count,
                    "中性": s.neutral_count,
                    "负面": s.negative_count,
                })
            df = pd.DataFrame(rows).sort_values("提及率%", ascending=False)

            st.dataframe(
                df.style.background_gradient(subset=["提及率%", "情感得分"], cmap="RdYlGn"),
                use_container_width=True, hide_index=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(
                    df, x="品牌", y="提及率%", color="是否我方",
                    color_discrete_map={"我方": "#2196F3", "竞品": "#FF9800"},
                    title="各品牌AI提及率对比",
                )
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig2 = px.scatter(
                    df[df["提及次数"] > 0], x="平均出现位置", y="情感得分",
                    size="提及次数", color="是否我方", text="品牌",
                    color_discrete_map={"我方": "#2196F3", "竞品": "#FF9800"},
                    title="位置 vs 情感矩阵（气泡=提及次数，位置越小越靠前）",
                )
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**AI原文引用片段**")
            for brand, s in stats.items():
                if s.snippets:
                    with st.expander(f"{brand}（{len(s.snippets)}条引用）"):
                        for snippet in s.snippets:
                            st.markdown(f"> {snippet}")

            st.markdown("---")
            st.subheader("AI引用来源分析")
            st.caption("AI 回答中引用了哪些内容来提及品牌（需要支持 citations 的引擎才有数据）")

            citations_data = aggregate_citations(runs, my_brands)
            if not citations_data:
                st.info("暂无引用来源数据。运行监测后，若 AI 返回引用URL则会在此展示。")
            else:
                col1, col2 = st.columns(2)
                df_cit = pd.DataFrame(citations_data[:15])
                with col1:
                    fig_cit = px.bar(
                        df_cit, x="count", y="domain", orientation="h",
                        title="各域名被AI引用次数（仅统计提及品牌时）",
                        color="count", color_continuous_scale="Blues",
                    )
                    fig_cit.update_layout(yaxis=dict(autorange="reversed"))
                    st.plotly_chart(fig_cit, use_container_width=True)
                with col2:
                    fig_pie = px.pie(
                        df_cit.head(8), values="count", names="domain",
                        title="引用来源分布（Top 8域名）",
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                st.markdown("**引用URL明细**")
                for entry in citations_data[:10]:
                    with st.expander(f"{entry['domain']}（{entry['count']}次引用）"):
                        for url in entry["urls"]:
                            st.markdown(f"- [{url}]({url})")


# ══════════════════════════════════════════════════════════
# TAB 3 · 提示词管理
# ══════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown("""
    <div class="geo-header" style="margin-bottom:16px">
      <div class="geo-header-icon">💬</div>
      <div>
        <h2>提示词管理</h2>
        <p>管理发给AI引擎的查询问题，追踪每条提示词的品牌提及效果</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _runs         = monitor_db.all_runs()
    _prompt_stats = compute_prompt_stats(_runs)
    _templates    = competitor_db.get_query_templates()
    _all_enabled  = competitor_db.get_all_enabled_queries()

    total_prompts   = sum(len(v) for v in _templates.values())
    enabled_count   = len(_all_enabled)

    # per-prompt mention rates for prompts that have run history
    _rates_with_data = [v["mention_rate"] for v in _prompt_stats.values() if v["total"] > 0]
    avg_mention_rate = round(sum(_rates_with_data) / len(_rates_with_data), 1) if _rates_with_data else 0
    best_prompt_rate = max(_rates_with_data) if _rates_with_data else 0
    best_prompt_text = ""
    if _rates_with_data:
        best_prompt_text = max(_prompt_stats, key=lambda q: _prompt_stats[q]["mention_rate"])

    # ── 概览指标 ────────────────────────────────────────────
    ov1, ov2, ov3, ov4 = st.columns(4)
    ov1.metric("提示词总数",   total_prompts)
    ov2.metric("已启用",       enabled_count, delta=f"禁用 {total_prompts - enabled_count}" if total_prompts - enabled_count else None, delta_color="off")
    ov3.metric("平均提及率",   f"{avg_mention_rate}%" if _rates_with_data else "暂无数据")
    ov4.metric("最佳提及率",   f"{best_prompt_rate}%" if _rates_with_data else "暂无数据")
    if best_prompt_text:
        st.caption(f"最佳提示词：{best_prompt_text[:60]}{'…' if len(best_prompt_text) > 60 else ''}")

    # ── 效果排行图 ──────────────────────────────────────────
    if _prompt_stats:
        st.markdown("---")
        st.subheader("📊 各提示词品牌提及率排行")
        st.caption("基于历史所有监测运行结果统计，提及率 = 该提示词下品牌被提及次数 / 运行总次数")

        chart_rows = []
        for stage, stage_label in STAGE_LABELS.items():
            for item in _templates.get(stage, []):
                q = item["text"]
                s = _prompt_stats.get(q, {"mention_count": 0, "total": 0, "mention_rate": 0})
                chart_rows.append({
                    "提示词":   q[:35] + ("…" if len(q) > 35 else ""),
                    "完整提示词": q,
                    "阶段":    stage_label,
                    "提及率%":  s["mention_rate"],
                    "运行次数":  s["total"],
                    "提及次数":  s["mention_count"],
                    "已启用":   item.get("enabled", True),
                })

        if chart_rows:
            chart_df = pd.DataFrame(chart_rows).sort_values("提及率%", ascending=True)
            fig_prompts = px.bar(
                chart_df, x="提及率%", y="提示词", orientation="h",
                color="阶段", text="提及率%",
                hover_data={"完整提示词": True, "运行次数": True, "提及次数": True, "提示词": False},
                color_discrete_sequence=["#42A5F5", "#66BB6A", "#FFA726"],
                height=max(300, len(chart_rows) * 36),
            )
            fig_prompts.update_traces(texttemplate="%{text}%", textposition="outside")
            fig_prompts.update_layout(showlegend=True, xaxis_range=[0, 110])
            st.plotly_chart(fig_prompts, use_container_width=True)
        else:
            st.info("运行「AI引擎监测」后，这里将展示每条提示词的品牌提及率排行。")

    # ── 按阶段管理提示词 ────────────────────────────────────
    st.markdown("---")
    st.subheader("🗂️ 提示词列表管理")

    stage_keys   = list(STAGE_LABELS.keys())
    stage_tabs_pm = st.tabs([STAGE_LABELS[s] for s in stage_keys])

    for _si, _stage in enumerate(stage_keys):
        with stage_tabs_pm[_si]:
            _stage_items = _templates.get(_stage, [])
            if not _stage_items:
                st.info(f"该阶段还没有提示词，在下方添加。")
            else:
                for _qi, _qitem in enumerate(_stage_items):
                    _q      = _qitem["text"]
                    _ps     = _prompt_stats.get(_q, {"mention_count": 0, "total": 0, "mention_rate": 0})
                    _enabled = _qitem.get("enabled", True)
                    _rate_str = f"{_ps['mention_rate']}%（{_ps['mention_count']}/{_ps['total']}次）" if _ps["total"] > 0 else "尚未运行"
                    _color = (
                        "#E8F5E9" if (_ps["total"] > 0 and _ps["mention_rate"] >= 50)
                        else "#FFF9C4" if (_ps["total"] > 0 and _ps["mention_rate"] > 0)
                        else "#F5F5F5"
                    )
                    _opacity = "1.0" if _enabled else "0.5"

                    st.markdown(
                        f"""<div style="background:{_color};border-radius:8px;padding:10px 14px;
                        margin-bottom:8px;opacity:{_opacity};border-left:4px solid
                        {'#4CAF50' if _ps.get('mention_rate',0)>=50 and _ps['total']>0
                         else '#FFC107' if _ps.get('mention_rate',0)>0 and _ps['total']>0
                         else '#BDBDBD'}">
                        <span style="font-size:0.95rem">{_q}</span><br>
                        <span style="font-size:0.78rem;color:#757575">提及率：{_rate_str}
                        {'　🔴 已禁用' if not _enabled else ''}</span>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    _c1, _c2, _c3 = st.columns([1, 1, 5])
                    _toggle_label = "禁用" if _enabled else "启用"
                    if _c1.button(_toggle_label, key=f"pm_toggle_{_qitem['id']}"):
                        competitor_db.toggle_query(_stage, _qitem["id"], not _enabled)
                        st.rerun()
                    if _c2.button("删除", key=f"pm_del_{_qitem['id']}"):
                        competitor_db.remove_query(_stage, _qitem["id"])
                        st.rerun()

            st.markdown("**添加新提示词**")
            with st.form(f"pm_add_{_stage}", clear_on_submit=True):
                _new_q = st.text_input(
                    "提示词内容", key=f"pm_new_{_stage}",
                    placeholder="输入发给AI的查询问题，例如：有哪些AI标书工具推荐？"
                )
                if st.form_submit_button("➕ 添加到本阶段"):
                    if _new_q.strip():
                        competitor_db.add_query(_stage, _new_q.strip())
                        st.success("已添加")
                        st.rerun()

    # ── 推荐词库 ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("💡 推荐提示词库")
    st.caption("基于GEO行业最佳实践整理，点击「一键添加」可直接加入对应阶段")

    for _stage, _stage_label in STAGE_LABELS.items():
        with st.expander(f"{_stage_label} — 推荐 {len(RECOMMENDED_PROMPTS.get(_stage, []))} 条"):
            _existing_texts = {item["text"] for item in _templates.get(_stage, [])}
            _recs = RECOMMENDED_PROMPTS.get(_stage, [])
            if not _recs:
                st.write("暂无推荐")
                continue
            for _rec in _recs:
                _rc1, _rc2 = st.columns([5, 1])
                _rc1.write(_rec)
                if _rec in _existing_texts:
                    _rc2.caption("已添加")
                else:
                    if _rc2.button("添加", key=f"rec_{_stage}_{hash(_rec)}"):
                        competitor_db.add_query(_stage, _rec)
                        st.success(f"已添加：{_rec[:30]}…")
                        st.rerun()

    # ── 批量操作 ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("⚡ 批量操作")
    _bc1, _bc2, _bc3 = st.columns(3)
    if _bc1.button("全部启用"):
        for _s in stage_keys:
            for _qi in _templates.get(_s, []):
                if not _qi.get("enabled", True):
                    competitor_db.toggle_query(_s, _qi["id"], True)
        st.success("已全部启用")
        st.rerun()
    if _bc2.button("全部禁用"):
        for _s in stage_keys:
            for _qi in _templates.get(_s, []):
                if _qi.get("enabled", True):
                    competitor_db.toggle_query(_s, _qi["id"], False)
        st.success("已全部禁用")
        st.rerun()
    with _bc3:
        st.caption(f"当前：{enabled_count}/{total_prompts} 条已启用")


# ══════════════════════════════════════════════════════════
# TAB 4 · 设置
# ══════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("设置")

    st.markdown("**我的品牌关键词**")
    my_brands_str = st.text_input(
        "品牌词（逗号分隔）", value=", ".join(competitor_db.get_my_brands())
    )
    st.markdown("**监测竞品列表**")
    competitors_str = st.text_input(
        "竞品名称（逗号分隔）", value=", ".join(competitor_db.get_competitors())
    )

    if st.button("保存品牌/竞品设置"):
        competitor_db.set_my_brands([b.strip() for b in my_brands_str.split(",") if b.strip()])
        competitor_db.set_competitors([c.strip() for c in competitors_str.split(",") if c.strip()])
        st.success("设置已保存")
        st.rerun()

    st.markdown("---")
    st.info("💬 提示词的添加、启用、删除和效果分析，请前往「💬 提示词管理」标签页。")

    st.markdown("---")
    st.markdown("**API Key 说明**")
    _has_env_key = bool(os.environ.get("SILICONFLOW_API_KEY", ""))
    if _has_env_key:
        st.success("API Key 已由服务器配置，AI 功能全局生效，无需手动填写。", icon="🔒")
    else:
        st.info(
            "本地运行时，在左侧边栏填写 SiliconFlow API Key 后全局生效。\n\n"
            "部署到 Streamlit Cloud 时，在 App Settings → Secrets 中添加：\n"
            "```\nSILICONFLOW_API_KEY = \"sk-xxxxxxxx\"\n```"
        )
