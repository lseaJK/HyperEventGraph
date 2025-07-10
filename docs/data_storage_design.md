# HyperEventGraph 数据存储结构设计

## 概述

本文档详细描述了HyperEventGraph项目的数据存储架构设计，涵盖从原始文本到知识图谱的完整数据流程。设计遵循分层架构原则，确保数据的一致性、可扩展性和高效检索。

## 1. 数据存储架构总览

```
HyperEventGraph/
├── data/                           # 数据根目录
│   ├── raw_texts/                  # 原始文本存储层
│   ├── processed_texts/            # 预处理文本存储层
│   ├── extracted_events/           # 事件JSON存储层
│   ├── unique_contexts/            # HyperGraphRAG格式存储层
│   ├── knowledge_graph/            # 知识图谱存储层
│   ├── indexes/                    # 索引文件存储
│   ├── metadata/                   # 元数据存储
│   └── backups/                    # 备份存储
├── config/                         # 配置文件
│   ├── storage_config.json         # 存储配置
│   ├── index_config.json           # 索引配置
│   └── backup_config.json          # 备份配置
└── logs/                           # 日志文件
    ├── storage_operations.log      # 存储操作日志
    ├── data_quality.log            # 数据质量日志
    └── backup_operations.log       # 备份操作日志
```

## 2. 原始文本存储结构设计 (1.3.1)

### 2.1 目录结构规范

```
data/raw_texts/
├── financial/                      # 金融领域
│   ├── 2024/                       # 年份
│   │   ├── 01/                     # 月份
│   │   │   ├── news/               # 新闻来源
│   │   │   │   ├── sina_finance/   # 具体网站
│   │   │   │   ├── eastmoney/
│   │   │   │   └── wallstreetcn/
│   │   │   ├── announcements/      # 公告来源
│   │   │   │   ├── sse/            # 上交所
│   │   │   │   ├── szse/           # 深交所
│   │   │   │   └── csrc/           # 证监会
│   │   │   └── reports/            # 研报来源
│   │   │       ├──券商研报/
│   │   │       └── 第三方研究/
│   │   └── 02/
│   └── 2023/
└── circuit/                        # 集成电路领域
    ├── 2024/
    │   ├── 01/
    │   │   ├── news/
    │   │   │   ├── eeworld/
    │   │   │   ├── eet_china/
    │   │   │   └── semiconductor_today/
    │   │   ├── industry_reports/
    │   │   └── patent_documents/
    │   └── 02/
    └── 2023/
```

### 2.2 文件命名规范

```
格式: {domain}_{source}_{date}_{sequence}_{hash}.{ext}
示例: financial_sina_20240115_001_a1b2c3d4.txt
      circuit_eeworld_20240115_002_e5f6g7h8.pdf

字段说明:
- domain: 领域标识 (financial/circuit)
- source: 数据源标识
- date: 采集日期 (YYYYMMDD)
- sequence: 当日序号 (001-999)
- hash: 内容哈希前8位 (用于去重)
- ext: 文件扩展名
```

### 2.3 元数据结构

每个原始文本文件对应一个元数据JSON文件：

```json
{
    "file_id": "financial_sina_20240115_001_a1b2c3d4",
    "domain": "financial",
    "source": {
        "name": "新浪财经",
        "url": "https://finance.sina.com.cn/article/123456",
        "type": "news"
    },
    "collection_info": {
        "collected_at": "2024-01-15T10:30:00Z",
        "collector_version": "1.0.0",
        "collection_method": "web_scraping"
    },
    "content_info": {
        "title": "某公司宣布重大并购计划",
        "author": "张三",
        "publish_date": "2024-01-15",
        "language": "zh-CN",
        "encoding": "utf-8",
        "word_count": 1500,
        "content_hash": "a1b2c3d4e5f6g7h8"
    },
    "quality_metrics": {
        "completeness_score": 0.95,
        "readability_score": 0.88,
        "relevance_score": 0.92
    },
    "processing_status": {
        "preprocessed": false,
        "events_extracted": false,
        "graph_integrated": false
    }
}
```

## 3. 事件JSON存储结构设计 (1.3.2)

### 3.1 存储目录结构

```
data/extracted_events/
├── financial/
│   ├── company_merger_and_acquisition/
│   │   ├── 2024/
│   │   │   ├── 01/
│   │   │   │   ├── events_20240115.jsonl
│   │   │   │   └── events_20240116.jsonl
│   │   │   └── 02/
│   │   └── 2023/
│   ├── investment_and_financing/
│   ├── executive_change/
│   └── legal_proceeding/
└── circuit/
    ├── capacity_expansion/
    ├── technological_breakthrough/
    ├── supply_chain_dynamics/
    ├── collaboration_joint_venture/
    └── intellectual_property/
```

### 3.2 事件JSON格式规范

基于event_schemas.json，每个事件包含以下标准字段：

```json
{
    "event_id": "evt_financial_ma_20240115_001",
    "extraction_info": {
        "extracted_at": "2024-01-15T11:00:00Z",
        "extractor_version": "1.0.0",
        "source_file_id": "financial_sina_20240115_001_a1b2c3d4",
        "confidence_score": 0.92,
        "extraction_method": "llm_based"
    },
    "event_data": {
        "event_type": "公司并购",
        "acquirer": "腾讯控股",
        "acquired": "某游戏公司",
        "deal_amount": 5000000000,
        "status": "进行中",
        "announcement_date": "2024-01-15",
        "source": "新浪财经"
    },
    "entities": {
        "companies": ["腾讯控股", "某游戏公司"],
        "persons": [],
        "locations": ["深圳"],
        "amounts": [5000000000]
    },
    "relations": [
        {
            "subject": "腾讯控股",
            "predicate": "收购",
            "object": "某游戏公司",
            "confidence": 0.95
        }
    ],
    "validation": {
        "schema_valid": true,
        "human_reviewed": false,
        "quality_score": 0.88
    }
}
```

### 3.3 索引结构设计

```
data/indexes/events/
├── by_entity/
│   ├── companies.json              # 公司实体索引
│   ├── persons.json                # 人员实体索引
│   └── locations.json              # 地点实体索引
├── by_time/
│   ├── daily_index.json            # 按日索引
│   ├── monthly_index.json          # 按月索引
│   └── yearly_index.json           # 按年索引
├── by_type/
│   ├── event_type_index.json       # 按事件类型索引
│   └── domain_index.json           # 按领域索引
└── by_source/
    ├── source_index.json           # 按来源索引
    └── quality_index.json          # 按质量分级索引
```

## 4. unique_contexts转换格式规范 (1.3.3)

### 4.1 转换目标格式

基于HyperGraphRAG的要求，将事件JSON转换为unique_contexts格式：

```json
[
    {
        "context_id": "ctx_evt_financial_ma_20240115_001",
        "content": "腾讯控股于2024年1月15日宣布收购某游戏公司，交易金额达50亿元人民币。此次并购旨在加强腾讯在游戏领域的市场地位。收购方为腾讯控股，被收购方为某游戏公司，交易状态为进行中。",
        "metadata": {
            "event_id": "evt_financial_ma_20240115_001",
            "event_type": "公司并购",
            "domain": "financial",
            "entities": ["腾讯控股", "某游戏公司"],
            "timestamp": "2024-01-15",
            "source": "新浪财经",
            "confidence": 0.92
        },
        "hyperedges": [
            {
                "edge_id": "he_ma_001",
                "edge_type": "merger_acquisition_event",
                "nodes": ["腾讯控股", "某游戏公司", "2024-01-15", "50亿元"],
                "edge_attributes": {
                    "status": "进行中",
                    "announcement_date": "2024-01-15"
                }
            }
        ]
    }
]
```

### 4.2 转换规则

1. **内容生成规则**：
   - 将结构化事件数据转换为自然语言描述
   - 保持关键信息的完整性和准确性
   - 使用标准化的表达模板

2. **超边构建规则**：
   - 事件作为超边连接多个实体节点
   - 实体包括：公司、人员、地点、时间、金额等
   - 边属性包含事件的详细信息

3. **元数据映射规则**：
   - 保留原始事件的所有关键信息
   - 添加转换过程的追踪信息
   - 维护数据血缘关系

### 4.3 存储结构

```
data/unique_contexts/
├── financial/
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── contexts_20240115.json
│   │   │   └── contexts_20240116.json
│   │   └── 02/
│   └── 2023/
├── circuit/
│   ├── 2024/
│   └── 2023/
└── combined/
    ├── daily_contexts/
    ├── weekly_contexts/
    └── monthly_contexts/
```

## 5. 数据版本管理机制 (1.3.4)

### 5.1 版本控制策略

```
data/metadata/versions/
├── schema_versions/
│   ├── event_schemas_v1.0.0.json
│   ├── event_schemas_v1.1.0.json
│   └── current -> event_schemas_v1.1.0.json
├── data_versions/
│   ├── raw_texts/
│   │   ├── v1.0.0/
│   │   │   ├── manifest.json
│   │   │   └── checksums.md5
│   │   └── v1.1.0/
│   ├── extracted_events/
│   └── unique_contexts/
└── processing_versions/
    ├── extractor_v1.0.0/
    ├── extractor_v1.1.0/
    └── converter_v1.0.0/
```

### 5.2 版本清单格式

```json
{
    "version": "1.1.0",
    "created_at": "2024-01-15T12:00:00Z",
    "description": "添加新的事件类型支持",
    "changes": [
        {
            "type": "schema_update",
            "description": "新增知识产权事件类型",
            "affected_files": ["event_schemas.json"]
        },
        {
            "type": "data_addition",
            "description": "新增1000条金融事件数据",
            "affected_paths": ["extracted_events/financial/"]
        }
    ],
    "statistics": {
        "total_files": 15420,
        "total_events": 89650,
        "total_size_mb": 2048
    },
    "compatibility": {
        "backward_compatible": true,
        "migration_required": false
    },
    "checksums": {
        "md5": "a1b2c3d4e5f6g7h8",
        "sha256": "1234567890abcdef"
    }
}
```

### 5.3 版本管理操作

1. **版本创建**：
   - 自动生成版本号（语义化版本控制）
   - 计算数据完整性校验和
   - 记录变更日志

2. **版本回滚**：
   - 支持回滚到任意历史版本
   - 自动处理依赖关系
   - 保证数据一致性

3. **版本比较**：
   - 提供版本间差异对比
   - 支持增量更新
   - 变更影响分析

## 6. 数据备份和恢复策略 (1.3.5)

### 6.1 备份策略

```
data/backups/
├── full_backups/                   # 全量备份
│   ├── 2024-01-15_full.tar.gz
│   ├── 2024-01-08_full.tar.gz
│   └── 2024-01-01_full.tar.gz
├── incremental_backups/            # 增量备份
│   ├── 2024-01-16_inc.tar.gz
│   ├── 2024-01-17_inc.tar.gz
│   └── 2024-01-18_inc.tar.gz
├── differential_backups/           # 差异备份
│   ├── 2024-01-16_diff.tar.gz
│   └── 2024-01-17_diff.tar.gz
└── backup_manifests/               # 备份清单
    ├── backup_manifest_20240115.json
    └── backup_manifest_20240116.json
```

### 6.2 备份配置

```json
{
    "backup_config": {
        "schedule": {
            "full_backup": "weekly",
            "incremental_backup": "daily",
            "differential_backup": "daily"
        },
        "retention_policy": {
            "full_backups": "3_months",
            "incremental_backups": "1_month",
            "differential_backups": "1_month"
        },
        "compression": {
            "algorithm": "gzip",
            "level": 6
        },
        "encryption": {
            "enabled": true,
            "algorithm": "AES-256"
        },
        "storage_locations": [
            {
                "type": "local",
                "path": "/data/backups/"
            },
            {
                "type": "cloud",
                "provider": "aws_s3",
                "bucket": "hypereventgraph-backups"
            }
        ]
    }
}
```

### 6.3 恢复策略

1. **完整恢复**：
   - 从最近的全量备份恢复
   - 应用后续的增量备份
   - 验证数据完整性

2. **部分恢复**：
   - 支持按时间范围恢复
   - 支持按数据类型恢复
   - 支持按领域恢复

3. **灾难恢复**：
   - 多地备份策略
   - 自动故障检测
   - 快速切换机制

## 7. 数据质量控制

### 7.1 质量指标

```json
{
    "quality_metrics": {
        "completeness": {
            "required_fields_present": 0.98,
            "data_coverage": 0.95
        },
        "accuracy": {
            "schema_compliance": 0.99,
            "data_validation_pass_rate": 0.97
        },
        "consistency": {
            "cross_reference_validity": 0.96,
            "temporal_consistency": 0.94
        },
        "timeliness": {
            "processing_delay_hours": 2.5,
            "data_freshness_score": 0.92
        }
    }
}
```

### 7.2 质量监控

1. **实时监控**：
   - 数据摄入质量检查
   - 处理过程异常检测
   - 质量指标实时计算

2. **定期审核**：
   - 数据一致性检查
   - 重复数据检测
   - 数据完整性验证

3. **质量报告**：
   - 日/周/月质量报告
   - 质量趋势分析
   - 问题根因分析

## 8. 性能优化

### 8.1 存储优化

1. **分区策略**：
   - 按时间分区
   - 按领域分区
   - 按数据大小分区

2. **压缩策略**：
   - 文本数据压缩
   - 索引文件压缩
   - 备份数据压缩

3. **缓存策略**：
   - 热数据内存缓存
   - 索引文件缓存
   - 查询结果缓存

### 8.2 检索优化

1. **多级索引**：
   - 主键索引
   - 复合索引
   - 全文索引

2. **查询优化**：
   - 查询计划优化
   - 并行查询支持
   - 结果集分页

## 9. 安全控制

### 9.1 访问控制

```json
{
    "access_control": {
        "roles": {
            "admin": ["read", "write", "delete", "backup", "restore"],
            "developer": ["read", "write"],
            "analyst": ["read"],
            "viewer": ["read_limited"]
        },
        "data_classification": {
            "public": ["raw_texts/news"],
            "internal": ["extracted_events", "unique_contexts"],
            "confidential": ["metadata", "backups"]
        }
    }
}
```

### 9.2 数据保护

1. **加密存储**：
   - 敏感数据加密
   - 传输加密
   - 密钥管理

2. **审计日志**：
   - 访问日志记录
   - 操作日志记录
   - 异常行为检测

## 10. 实施计划

### 10.1 实施阶段

1. **第一阶段**（1-2天）：
   - 创建基础目录结构
   - 实现基本的文件存储功能
   - 建立元数据管理机制

2. **第二阶段**（2-3天）：
   - 实现事件JSON存储
   - 建立索引机制
   - 实现基本的查询功能

3. **第三阶段**（2-3天）：
   - 实现unique_contexts转换
   - 建立版本管理系统
   - 实现备份恢复功能

4. **第四阶段**（1-2天）：
   - 性能优化
   - 安全控制实施
   - 系统测试和验证

### 10.2 验收标准

1. **功能验收**：
   - 所有存储功能正常工作
   - 数据格式符合规范
   - 索引和查询性能满足要求

2. **质量验收**：
   - 数据完整性100%
   - 备份恢复成功率100%
   - 系统稳定性满足要求

3. **性能验收**：
   - 数据写入速度 > 1000条/秒
   - 查询响应时间 < 100ms
   - 存储空间利用率 > 80%

## 11. 总结

本设计文档提供了HyperEventGraph项目完整的数据存储架构方案，涵盖了从原始文本到知识图谱的全流程数据管理。通过分层架构、标准化格式、完善的版本管理和备份策略，确保了数据的安全性、一致性和可扩展性。

该架构设计将为后续的事件抽取、知识图谱构建和智能应用开发提供坚实的数据基础。