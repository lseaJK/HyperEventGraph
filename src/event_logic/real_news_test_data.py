#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实新闻数据测试集
用于测试事件逻辑分析器的真实数据处理能力
"""

# 2024年真实新闻事件数据
REAL_NEWS_EVENTS = [
    {
        "id": "news_001",
        "title": "2024年中国经济下行压力加大",
        "content": "2024年中国经济面临多重挑战，包括房地产市场调整、消费需求疲软、出口增长放缓等因素。政府出台多项稳增长政策，包括降准降息、财政刺激等措施。",
        "timestamp": "2024-11-01T10:00:00Z",
        "source": "环球时报",
        "category": "经济",
        "location": "中国",
        "entities": ["中国经济", "房地产市场", "消费需求", "出口", "货币政策", "财政政策"]
    },
    {
        "id": "news_002",
        "title": "特朗普赢得2024年美国总统大选",
        "content": "特朗普在2024年美国总统大选中获胜，获得312张选举人票。共和党同时控制参众两院，这将为美国外交政策带来重大变化，包括对俄乌冲突和中东局势的影响。",
        "timestamp": "2024-11-06T08:00:00Z",
        "source": "知乎专栏",
        "category": "政治",
        "location": "美国",
        "entities": ["特朗普", "美国大选", "共和党", "外交政策", "俄乌冲突", "中东"]
    },
    {
        "id": "news_003",
        "title": "俄乌冲突战场态势变化",
        "content": "俄军在多个方向取得进展，包括占领科皮斯尼基夫卡村、克列门纳亚巴尔卡村等地。乌军总司令表示正在准备从库尔斯克州撤军。战场态势对俄军有利。",
        "timestamp": "2024-11-08T12:00:00Z",
        "source": "知乎专栏",
        "category": "军事",
        "location": "乌克兰",
        "entities": ["俄军", "乌军", "科皮斯尼基夫卡", "库尔斯克", "军事行动"]
    },
    {
        "id": "news_004",
        "title": "德国政府联盟崩溃",
        "content": "德国总理舒尔茨解雇财政部长林德纳，原因是后者不愿向乌克兰拨款。红绿灯联盟实质上崩溃，德国总统表示准备批准提前选举。",
        "timestamp": "2024-11-07T14:00:00Z",
        "source": "知乎专栏",
        "category": "政治",
        "location": "德国",
        "entities": ["舒尔茨", "林德纳", "德国政府", "红绿灯联盟", "乌克兰援助", "提前选举"]
    },
    {
        "id": "news_005",
        "title": "2024年智能座舱芯片市场快速发展",
        "content": "2024年智能座舱芯片市场呈现快速发展态势，AI大模型赋能座舱体验升级。国内外厂商加速布局，技术革新推动市场竞争加剧。新能源汽车成为主要应用场景。",
        "timestamp": "2024-10-15T09:00:00Z",
        "source": "科技媒体",
        "category": "科技",
        "location": "全球",
        "entities": ["智能座舱", "芯片市场", "AI大模型", "新能源汽车", "技术革新"]
    },
    {
        "id": "news_006",
        "title": "巴以冲突持续升级",
        "content": "以色列继续在加沙地带的军事行动，巴勒斯坦平民伤亡持续增加。国际社会呼吁停火，但冲突各方立场分歧巨大。人道主义危机加剧。",
        "timestamp": "2024-11-05T16:00:00Z",
        "source": "国际新闻",
        "category": "国际",
        "location": "中东",
        "entities": ["以色列", "加沙地带", "巴勒斯坦", "军事行动", "人道主义危机", "国际社会"]
    },
    {
        "id": "news_007",
        "title": "中国新能源汽车出口创新高",
        "content": "2024年中国新能源汽车出口量创历史新高，主要出口到欧洲、东南亚等市场。比亚迪、特斯拉等品牌表现突出，推动中国汽车工业转型升级。",
        "timestamp": "2024-10-20T11:00:00Z",
        "source": "财经媒体",
        "category": "经济",
        "location": "中国",
        "entities": ["新能源汽车", "出口", "比亚迪", "特斯拉", "汽车工业", "转型升级"]
    },
    {
        "id": "news_008",
        "title": "人工智能技术在医疗领域应用加速",
        "content": "2024年人工智能在医疗诊断、药物研发、个性化治疗等领域应用加速。多家科技公司推出AI医疗产品，监管政策逐步完善，行业发展前景广阔。",
        "timestamp": "2024-09-30T13:00:00Z",
        "source": "科技日报",
        "category": "科技",
        "location": "全球",
        "entities": ["人工智能", "医疗诊断", "药物研发", "个性化治疗", "科技公司", "监管政策"]
    },
    {
        "id": "news_009",
        "title": "全球气候变化影响加剧",
        "content": "2024年全球多地遭遇极端天气事件，包括洪水、干旱、热浪等。联合国气候大会呼吁各国加强减排行动，推动绿色转型和可持续发展。",
        "timestamp": "2024-11-10T15:00:00Z",
        "source": "环境报",
        "category": "环境",
        "location": "全球",
        "entities": ["气候变化", "极端天气", "洪水", "干旱", "联合国", "减排", "绿色转型"]
    },
    {
        "id": "news_010",
        "title": "数字货币监管政策趋严",
        "content": "多国政府加强对数字货币的监管，出台相关法规限制投机交易。央行数字货币研发加速，传统金融机构积极布局数字资产业务。",
        "timestamp": "2024-10-25T10:30:00Z",
        "source": "金融时报",
        "category": "金融",
        "location": "全球",
        "entities": ["数字货币", "监管政策", "央行数字货币", "金融机构", "数字资产"]
    }
]

# 事件关系数据
REAL_EVENT_RELATIONS = [
    {
        "source_event": "news_002",
        "target_event": "news_003",
        "relation_type": "影响",
        "description": "特朗普当选可能影响俄乌冲突走向",
        "confidence": 0.8
    },
    {
        "source_event": "news_003",
        "target_event": "news_004",
        "relation_type": "关联",
        "description": "俄乌冲突导致德国政府在援助问题上分歧",
        "confidence": 0.7
    },
    {
        "source_event": "news_001",
        "target_event": "news_007",
        "relation_type": "促进",
        "description": "经济转型推动新能源汽车出口增长",
        "confidence": 0.6
    },
    {
        "source_event": "news_005",
        "target_event": "news_007",
        "relation_type": "支撑",
        "description": "智能座舱技术支撑新能源汽车发展",
        "confidence": 0.7
    },
    {
        "source_event": "news_008",
        "target_event": "news_005",
        "relation_type": "技术关联",
        "description": "AI技术在医疗和汽车领域的应用",
        "confidence": 0.5
    },
    {
        "source_event": "news_009",
        "target_event": "news_007",
        "relation_type": "推动",
        "description": "气候变化推动新能源汽车需求",
        "confidence": 0.8
    }
]

# 复杂事件网络（包含循环关系）
COMPLEX_EVENT_RELATIONS = [
    {
        "source_event": "news_002",
        "target_event": "news_004",
        "relation_type": "间接影响",
        "description": "美国政策变化影响欧洲政治格局",
        "confidence": 0.6
    },
    {
        "source_event": "news_004",
        "target_event": "news_003",
        "relation_type": "影响",
        "description": "德国政府变化影响对乌援助",
        "confidence": 0.7
    },
    {
        "source_event": "news_003",
        "target_event": "news_002",
        "relation_type": "反馈",
        "description": "战场态势变化影响美国政策",
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