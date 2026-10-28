"""
导入真实内容数据 - 标捷公众号已发布内容（共12条）
python seed_data.py
"""
import uuid
from data_model import ContentDB, ContentItem
from geo_engine import analyze_geo

db = ContentDB()

samples = [
    ContentItem(
        id=str(uuid.uuid4()),
        title="不同项目的标书目录怎么排？先选对生成方式",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-27",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标书目录", "标书生成", "投标文件"],
        summary="介绍不同类型项目的标书目录排列逻辑，以及如何选择合适的AI生成方式",
        views=5, likes=1, comments=0, shares=1,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="做标书的人，能犯多让自己意想不到的错？",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-26",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标书错误", "投标", "标书制作"],
        summary="盘点做标书过程中常见但意想不到的失误，提供规避方法",
        views=6, likes=0, comments=2, shares=0,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="不用再熬夜写标书啦，让AI替你加班！",
        platform="公众号",
        content_type="长视频",
        publish_date="2026-10-26",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "AI写标书", "智能标书", "标书生成"],
        summary="视频号内容：演示AI自动生成标书全流程，解放熬夜加班",
        views=7, likes=3, comments=0, shares=3,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="投标总踩跑？资深投标人总结的5条避坑干货",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-25",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "投标避坑", "投标方案", "招投标"],
        summary="资深投标人总结5条实战避坑经验，帮助中小企业提升中标率",
        views=6, likes=4, comments=0, shares=4,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="5分钟生成20万字！标捷智写：五步快速写出合规高分方案建议书",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-24",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标捷", "智能标书", "方案建议书", "标书生成"],
        summary="介绍标捷智写产品，展示五步快速生成20万字合规高分方案建议书的完整流程",
        views=23, likes=6, comments=0, shares=4,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="AI写标书，人员、工期总是前后对不上？生成前先做好这一步",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-23",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "AI写标书", "标书制作", "投标文件", "智能标书"],
        summary="解决AI生成标书时人员和工期数据前后矛盾的问题，介绍前置准备步骤",
        views=88, likes=6, comments=1, shares=6,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="双十一限时福利：标书免费编写，满意才收费。限时特价11.11元/份",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-22",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标书制作", "标捷", "智能标书"],
        summary="双十一活动推广，标书免费编写满意才收费，特价11.11元/份",
        views=6, likes=2, comments=0, shares=2,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="听句劝，别再靠人眼去翻那上百页的标书了，这活真的反人类",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-21",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标书制作", "招标文件", "投标文件"],
        summary="吐槽传统人工审阅标书的低效与痛苦，引出AI智能标书解决方案",
        views=14, likes=3, comments=0, shares=2,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="写标书，别再照搬旧目录了！目录的真正出处，是招标文件这三章",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-20",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标书目录", "招标文件", "标书制作", "投标文件"],
        summary="揭示标书目录应从招标文件中提取而非照搬旧模板，指出正确的目录来源三章",
        views=28, likes=5, comments=0, shares=4,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="标书写到凌晨还是漏评分点？标捷智写，五步搞定",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-19",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标捷", "智能标书", "标书生成", "评分标准"],
        summary="解决标书撰写遗漏评分点的痛点，介绍标捷智写五步快速完成标书",
        views=30, likes=9, comments=0, shares=5,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="新关注即送 | 免费领取「标书制作体验卡」",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-18",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标书制作", "标捷", "智能标书"],
        summary="新粉丝福利文章，关注即可免费领取标书制作体验卡",
        views=32, likes=11, comments=2, shares=3,
    ),
    ContentItem(
        id=str(uuid.uuid4()),
        title="你好，新朋友：标捷官方微信公众号正式开通",
        platform="公众号",
        content_type="软文",
        publish_date="2026-10-17",
        url="https://mp.weixin.qq.com/s/",
        keywords=["AI标书", "标捷", "智能标书", "标书生成"],
        summary="标捷官方公众号开通公告，介绍账号定位和后续内容规划",
        views=526, likes=17, comments=0, shares=38,
    ),
]

for item in samples:
    detail = analyze_geo(item)
    item.geo_score = detail.total
    item.geo_score_detail = detail.to_dict()
    db.save_item(item)
    print(f"已导入: [{item.platform}] {item.title[:28]}... GEO评分: {detail.total}")

print(f"\n共导入 {len(samples)} 条数据，运行 start.bat 查看仪表盘")
