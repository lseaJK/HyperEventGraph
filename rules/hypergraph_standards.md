# HyperGraphRAG 知识图谱标准规范

## 一、实体节点标准

### 1.1 节点格式规范
```json
{
  "id": "entity_{type}_{sequence}",
  "type": "{EntityType}",
  "name": "{实体名称}",
  "properties": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

### 1.2 实体类型定义
- **Company**: 公司实体
- **Person**: 人物实体
- **Product**: 产品实体
- **Event**: 事件实体
- **Location**: 地理位置实体
- **Technology**: 技术实体

### 1.3 实体示例
```json
{
  "id": "entity_company_001",
  "type": "Company",
  "name": "环球网",
  "properties": {
    "industry": "媒体",
    "founded_year": "2007",
    "description": "中国新闻网站",
    "headquarters": "北京"
  }
}
```

## 二、关系边标准

### 2.1 关系格式规范
```json
{
  "id": "relation_{sequence}",
  "type": "{RelationType}",
  "source": "{source_entity_id}",
  "target": "{target_entity_id}",
  "properties": {
    "timestamp": "YYYY-MM-DD",
    "confidence": 0.0-1.0,
    "source_text": "原始文本片段"
  }
}
```

### 2.2 关系类型定义
- **reports**: 报道关系
- **invests**: 投资关系
- **cooperates**: 合作关系
- **acquires**: 收购关系
- **employs**: 雇佣关系
- **develops**: 开发关系
- **produces**: 生产关系

### 2.3 关系示例
```json
{
  "id": "relation_001",
  "type": "reports",
  "source": "entity_company_001",
  "target": "entity_event_001",
  "properties": {
    "timestamp": "2024-01-15",
    "confidence": 0.95,
    "source_text": "环球网报道了该事件"
  }
}
```

## 三、事件超边标准

### 3.1 超边格式规范
```json
{
  "id": "hyperedge_{event_type}_{sequence}",
  "type": "{EventCategory}",
  "event_type": "{具体事件类型}",
  "entities": ["{entity_id1}", "{entity_id2}", ...],
  "properties": {
    "trigger_text": "触发文本",
    "timestamp": "YYYY-MM-DD",
    "location": "事件地点",
    "impact_level": "high|medium|low",
    "confidence": 0.0-1.0
  }
}
```

### 3.2 事件类别定义
- **BusinessEvent**: 商业事件
- **TechEvent**: 技术事件
- **FinancialEvent**: 金融事件
- **LegalEvent**: 法律事件
- **PersonnelEvent**: 人事事件

### 3.3 超边示例
```json
{
  "id": "hyperedge_business_001",
  "type": "BusinessEvent",
  "event_type": "产能扩张",
  "entities": ["entity_company_002", "entity_product_001", "entity_location_001"],
  "properties": {
    "trigger_text": "后续恐必须祭出更多降价优惠，才能填补产能",
    "timestamp": "2024-01-15",
    "location": "中国",
    "impact_level": "medium",
    "confidence": 0.85
  }
}
```

## 四、ID命名规范

### 4.1 实体ID格式
- 格式：`entity_{type}_{sequence}`
- 示例：`entity_company_001`, `entity_person_001`

### 4.2 关系ID格式
- 格式：`relation_{sequence}`
- 示例：`relation_001`, `relation_002`

### 4.3 超边ID格式
- 格式：`hyperedge_{category}_{sequence}`
- 示例：`hyperedge_business_001`, `hyperedge_tech_001`

## 五、质量控制标准

### 5.1 数据完整性
- 所有必填字段必须存在
- ID必须唯一且符合命名规范
- 时间戳必须为有效日期格式

### 5.2 一致性检查
- 实体类型与属性匹配
- 关系类型与连接实体类型兼容
- 事件类型与参与实体类型合理

### 5.3 置信度标准
- 0.9-1.0: 高置信度，明确提及
- 0.7-0.9: 中等置信度，推理得出
- 0.5-0.7: 低置信度，可能存在
- <0.5: 不建议采用

## 六、数据转换流程

1. **文本预处理**: 清理和标准化输入文本
2. **实体识别**: 使用NER工具识别候选实体
3. **实体标准化**: 去重、合并、标准化实体
4. **关系抽取**: 识别实体间的语义关系
5. **事件构建**: 将复杂事件表示为超边
6. **格式转换**: 转换为标准JSON格式
7. **质量验证**: 执行完整性和一致性检查
8. **图谱插入**: 将标准化数据插入HyperGraphRAG

此标准规范确保知识图谱的结构化、标准化和高质量。