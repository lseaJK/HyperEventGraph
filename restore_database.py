#!/usr/bin/env python3
"""
从Neo4j恢复数据库状态并重新开始事理图谱构建
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager

def seed_database_from_neo4j():
    """从Neo4j中的数据重新填充SQLite数据库"""
    print("🔄 从Neo4j恢复数据库状态\n")
    
    # 加载配置
    config_path = project_root / "config.yaml"
    load_config(config_path)
    config = get_config()
    
    # 连接数据库
    db_path = config.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)
    
    try:
        # 连接Neo4j
        from src.storage.neo4j_event_storage import Neo4jEventStorage, Neo4jConfig
        
        neo4j_config = Neo4jConfig(
            uri=config['storage']['neo4j']['uri'],
            username=config['storage']['neo4j']['user'], 
            password=config['storage']['neo4j']['password']
        )
        neo4j = Neo4jEventStorage(neo4j_config)
        
        print("📊 从Neo4j获取事件数据...")
        
        # 获取所有事件
        with neo4j.driver.session() as session:
            # 获取事件节点和基本信息
            result = session.run("""
                MATCH (e:Event)
                RETURN e.id as event_id, 
                       e.description as description,
                       e.event_type as event_type,
                       e.source_text as source_text
                LIMIT 100
            """)
            
            events = []
            for record in result:
                events.append({
                    'id': record['event_id'],
                    'description': record['description'] or '',
                    'event_type': record['event_type'] or '',
                    'source_text': record['source_text'] or record['description'] or 'Neo4j恢复数据'
                })
        
        print(f"✅ 从Neo4j获取到 {len(events)} 个事件")
        
        if not events:
            print("❌ Neo4j中没有找到事件数据")
            return False
        
        # 将事件数据插入SQLite数据库
        print("💾 将数据插入SQLite数据库...")
        
        for i, event in enumerate(events):
            try:
                # 插入到master_state表，设置为completed状态
                db_manager.insert_record(
                    id=event['id'],
                    source_text=event['source_text'],
                    status='completed',
                    assigned_event_type=event['event_type'],
                    triage_confidence=0.9
                )
                
                if (i + 1) % 20 == 0:
                    print(f"   已处理 {i + 1}/{len(events)} 条记录...")
                    
            except Exception as e:
                # 可能是重复记录，跳过
                continue
        
        # 检查插入结果
        status_summary = db_manager.get_status_summary()
        print(f"\n✅ 数据库恢复完成!")
        print("📊 当前状态分布:")
        
        for status, count in status_summary.items():
            print(f"  {status}: {count:,}")
        
        neo4j.close()
        return True
        
    except Exception as e:
        print(f"❌ 恢复失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_seed_data():
    """创建一些测试数据来验证流程"""
    print("🌱 创建种子数据进行测试\n")
    
    # 加载配置
    config_path = project_root / "config.yaml"
    load_config(config_path)
    config = get_config()
    
    db_path = config.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)
    
    # 创建一些测试事件
    test_events = [
        {
            'id': 'test_001',
            'source_text': '某科技公司宣布新产品发布，预期将带来显著收入增长。',
            'event_type': '产品发布',
            'status': 'pending_clustering'
        },
        {
            'id': 'test_002', 
            'source_text': '该公司CEO在财报会议上表示对未来前景充满信心。',
            'event_type': '管理层表态',
            'status': 'pending_clustering'
        },
        {
            'id': 'test_003',
            'source_text': '分析师上调了该公司的目标价格，从100元调至120元。',
            'event_type': '分析师评级',
            'status': 'pending_clustering'
        },
        {
            'id': 'test_004',
            'source_text': '公司签署了价值10亿的大型合同，业务拓展取得重大进展。',
            'event_type': '业务合作',
            'status': 'pending_clustering'
        },
        {
            'id': 'test_005',
            'source_text': '受新产品发布影响，公司股价上涨了15%，创下年内新高。',
            'event_type': '股价变动',
            'status': 'pending_clustering'
        }
    ]
    
    print("💾 插入测试数据...")
    
    for event in test_events:
        try:
            db_manager.insert_record(
                id=event['id'],
                source_text=event['source_text'],
                status=event['status'],
                assigned_event_type=event['event_type'],
                triage_confidence=0.85
            )
        except Exception as e:
            print(f"插入 {event['id']} 失败: {e}")
            continue
    
    # 检查结果
    status_summary = db_manager.get_status_summary()
    print(f"\n✅ 种子数据创建完成!")
    print("📊 当前状态分布:")
    
    for status, count in status_summary.items():
        print(f"  {status}: {count:,}")
    
    print("\n🚀 现在可以运行 temp_cortex.py 来测试Cortex工作流!")
    
    return True

def main():
    print("🔄 数据库恢复和重建\n")
    
    print("选择恢复方式:")
    print("1. 从Neo4j恢复数据 (如果Neo4j中有数据)")
    print("2. 创建种子测试数据")
    
    # 直接尝试从Neo4j恢复
    print("\n尝试从Neo4j恢复数据...")
    neo4j_success = seed_database_from_neo4j()
    
    if not neo4j_success:
        print("\nNeo4j恢复失败，创建种子测试数据...")
        create_seed_data()
    
    print(f"\n🎉 数据库重建完成!")
    print("下一步可以运行:")
    print("  python temp_cortex.py")
    print("  或")
    print("  python run_cortex_workflow.py")

if __name__ == "__main__":
    main()
