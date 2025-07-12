#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实新闻数据测试集
用于测试事件逻辑分析器的真实数据处理能力
"""

# 2024年集成电路和芯片行业真实新闻事件数据
REAL_NEWS_EVENTS = [
    {
        "id": "news_001",
        "title": "2024年中国集成电路行业市场规模将达到14313亿元",
        "content": "2023年中国集成电路(芯片)行业市场规模达到12277亿元，五年复合增速达到13.45%。初步估算，2024年中国集成电路(芯片)行业市场规模将达到14313亿元。逻辑芯片应用份额占比最大达到54%。",
        "timestamp": "2024-01-20T10:00:00Z",
        "source": "前瞻产业研究院",
        "category": "科技",
        "location": "中国",
        "entities": ["集成电路", "芯片", "市场规模", "逻辑芯片", "中国"]
    },
    {
        "id": "news_002",
        "title": "全球半导体产业格局生变 AI推动产业发展",
        "content": "人工智能技术新一轮爆发式发展正在改变全球半导体产业格局。SEMI预计今年半导体销售额将增长约13%至16%，可能达到6000亿美元，预计到2030年前后有望实现1万亿美元里程碑。",
        "timestamp": "2024-04-29T08:00:00Z",
        "source": "新华网",
        "category": "科技",
        "location": "全球",
        "entities": ["半导体", "人工智能", "AI", "产业格局", "销售额"]
    },
    {
        "id": "news_003",
        "title": "英伟达推出Blackwell架构AI芯片B200",
        "content": "英伟达推出基于Blackwell架构的高性能GPU B200，集成2080亿个晶体管，是上一代芯片的2.6倍，在处理聊天机器人任务时速度比上一代快30倍。微软、亚马逊、谷歌等将是首批用户。",
        "timestamp": "2024-03-18T12:00:00Z",
        "source": "经济参考报",
        "category": "科技",
        "location": "美国",
        "entities": ["英伟达", "Blackwell", "AI芯片", "GPU", "晶体管"]
    },
    {
        "id": "news_004",
        "title": "日本重燃半导体雄心 台积电熊本工厂开业",
        "content": "台积电位于日本熊本县的工厂2月下旬开业，采用22/28纳米以及12/16纳米制程技术。日本政府为该工厂提供4760亿日元补贴，占总支出约37%。日本计划到2030年将国产芯片销售额提高两倍。",
        "timestamp": "2024-02-25T14:00:00Z",
        "source": "新华网",
        "category": "科技",
        "location": "日本",
        "entities": ["台积电", "日本", "熊本工厂", "半导体", "政府补贴"]
    },
    {
        "id": "news_005",
        "title": "中国半导体企业技术突破加速",
        "content": "中芯国际是中国最大的半导体代工厂，主要提供28纳米至14纳米制程。华为海思专注于芯片设计，推出Kirin系列和5G芯片。随着国家政策支持和技术进步，中国芯片企业正在加速技术突破。",
        "timestamp": "2024-01-20T09:00:00Z",
        "source": "前瞻产业研究院",
        "category": "科技",
        "location": "中国",
        "entities": ["中芯国际", "华为海思", "半导体代工", "芯片设计", "技术突破"]
    },
    {
        "id": "news_006",
        "title": "2024年智能座舱芯片市场快速发展",
        "content": "2024年智能座舱芯片市场呈现快速发展态势，AI大模型赋能座舱体验升级。国内外厂商加速布局，技术革新推动市场竞争加剧。新能源汽车成为主要应用场景。",
        "timestamp": "2024-10-15T16:00:00Z",
        "source": "科技媒体",
        "category": "科技",
        "location": "全球",
        "entities": ["智能座舱", "芯片市场", "AI大模型", "新能源汽车", "技术革新"]
    },
    {
        "id": "news_007",
        "title": "全球芯片供应链重构加速",
        "content": "受地缘政治影响，全球芯片供应链正在重构。美国、欧盟、日本等加大本土芯片制造投资，中国也在加强自主可控芯片产业链建设。供应链多元化成为趋势。",
        "timestamp": "2024-05-10T11:00:00Z",
        "source": "财经媒体",
        "category": "科技",
        "location": "全球",
        "entities": ["芯片供应链", "地缘政治", "本土制造", "自主可控", "供应链重构"]
    },
    {
        "id": "news_008",
        "title": "存储芯片市场回暖 价格企稳上涨",
        "content": "2024年存储芯片市场逐步回暖，DRAM和NAND Flash价格企稳上涨。三星、SK海力士、美光等主要厂商产能利用率提升，行业库存水平回归正常。",
        "timestamp": "2024-06-15T13:00:00Z",
        "source": "科技日报",
        "category": "科技",
        "location": "全球",
        "entities": ["存储芯片", "DRAM", "NAND Flash", "三星", "SK海力士", "美光"]
    },
    {
        "id": "news_009",
        "title": "汽车芯片短缺问题逐步缓解",
        "content": "经过两年多的供应紧张，汽车芯片短缺问题在2024年逐步缓解。车企加强与芯片厂商合作，建立更稳定的供应关系。新能源汽车对高性能芯片需求持续增长。",
        "timestamp": "2024-07-20T15:00:00Z",
        "source": "汽车工业报",
        "category": "科技",
        "location": "全球",
        "entities": ["汽车芯片", "供应短缺", "车企", "新能源汽车", "高性能芯片"]
    },
    {
        "id": "news_010",
        "title": "量子芯片技术取得重大突破",
        "content": "2024年量子芯片技术取得重大突破，IBM、谷歌、中科院等机构在量子比特数量和稳定性方面实现显著提升。量子计算商业化应用前景更加明朗。",
        "timestamp": "2024-08-25T10:30:00Z",
        "source": "科学技术报",
        "category": "科技",
        "location": "全球",
        "entities": ["量子芯片", "量子比特", "IBM", "谷歌", "中科院", "量子计算"]
    }
]

# 事件关系数据
REAL_EVENT_RELATIONS = [
    {
        "source_event": "news_002",
        "target_event": "news_003",
        "relation_type": "causal",
        "description": "AI技术发展推动英伟达芯片创新",
        "confidence": 0.8
    },
    {
        "source_event": "news_003",
        "target_event": "news_004",
        "relation_type": "correlation",
        "description": "英伟达芯片技术与台积电制造工艺相关",
        "confidence": 0.7
    },
    {
        "source_event": "news_001",
        "target_event": "news_006",
        "relation_type": "causal",
        "description": "集成电路发展推动智能座舱芯片市场",
        "confidence": 0.6
    },
    {
        "source_event": "news_006",
        "target_event": "news_009",
        "relation_type": "causal",
        "description": "智能座舱芯片需求推动汽车芯片市场发展",
        "confidence": 0.7
    },
    {
        "source_event": "news_002",
        "target_event": "news_005",
        "relation_type": "correlation",
        "description": "全球半导体发展与中国企业技术突破相关",
        "confidence": 0.5
    },
    {
        "source_event": "news_007",
        "target_event": "news_008",
        "relation_type": "causal",
        "description": "供应链重构影响存储芯片市场",
        "confidence": 0.8
    }
]

# 复杂事件网络（包含循环关系）
COMPLEX_EVENT_RELATIONS = [
    {
        "source_event": "news_002",
        "target_event": "news_004",
        "relation_type": "causal_indirect",
        "description": "全球半导体发展间接影响日本半导体政策",
        "confidence": 0.6
    },
    {
        "source_event": "news_004",
        "target_event": "news_003",
        "relation_type": "causal",
        "description": "台积电日本工厂影响英伟达芯片供应链",
        "confidence": 0.7
    },
    {
        "source_event": "news_003",
        "target_event": "news_002",
        "relation_type": "causal",
        "description": "英伟达芯片创新推动全球半导体市场发展",
        "confidence": 0.5
    }
]

def get_test_events():
    """获取测试事件数据"""
    return REAL_NEWS_EVENTS

def get_test_relations():
    """获取测试关系数据"""
    return REAL_EVENT_RELATIONS

def get_complex_relations():
    """获取复杂关系数据（包含循环）"""
    return COMPLEX_EVENT_RELATIONS

def get_all_test_data():
    """获取所有测试数据"""
    return {
        "events": REAL_NEWS_EVENTS,
        "relations": REAL_EVENT_RELATIONS,
        "complex_relations": COMPLEX_EVENT_RELATIONS
    }

if __name__ == "__main__":
    # 打印数据统计
    print(f"真实新闻事件数量: {len(REAL_NEWS_EVENTS)}")
    print(f"事件关系数量: {len(REAL_EVENT_RELATIONS)}")
    print(f"复杂关系数量: {len(COMPLEX_EVENT_RELATIONS)}")
    
    # 打印事件类别分布
    categories = {}
    for event in REAL_NEWS_EVENTS:
        cat = event["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\n事件类别分布:")
    for cat, count in categories.items():
        print(f"  {cat}: {count}")