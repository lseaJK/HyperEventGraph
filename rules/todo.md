# 事件提取与 Schema 定义 - 待办事项

- [ ] 1. 需求分析：定义事件抽取的输入数据源与格式。
- [ ] 2. Schema 设计：设计事件的 JSON Schema 并创建 `src/schema.json`。
- [ ] 3. 核心模块：创建 `src/data_processor.py` 用于处理数据。
- [ ] 4. TDD - 事件抽取：在 `tests/test_data_processor.py` 中编写测试用例。
- [ ] 5. 功能实现 - 事件抽取：在 `src/data_processor.py` 中实现核心逻辑。
- [ ] 6. TDD - Schema 验证：在 `tests/test_data_processor.py` 中编写测试用例。
- [ ] 7. 功能实现 - Schema 验证：在 `src/data_processor.py` 中实现验证逻辑。
- [ ] 8. 文档：更新 `rules/architecture.md` 以反映最终的设计。


## 阶段目标
根据用户反馈，明确任务为定义事件提取的 Schema、创建示例，并完善项目规则文档。

## 任务列表

- [ ] **任务1：完善项目规则**
    - [ ] 创建 `rules/project_rules.md` 文件，并写入项目规范。

- [ ] **任务2：定义“合作合资”事件 Schema**
    - [ ] 在 `rules/architecture.md` 中为“合作合资”事件类型定义详细的 JSON Schema。
    - [ ] Schema 应包含 `event_type`, `trigger_words`, `partners`, `domain`, `method`, `goal`, `validity_period`, `source`, `publish_date` 等字段。

- [ ] **任务3：创建事件提取示例**
    - [ ] 创建 `data` 目录用于存放提取的事件数据。
    - [ ] 根据定义的“合作合资” Schema，从一条示例新闻中提取信息。
    - [ ] 将提取的事件以 JSON 格式写入 `data/cooperation_joint_venture.jsonl` 文件。

- [ ] **任务4：知识库归档**
    - [ ] 将“合作合资”的 Schema 定义保存到长期知识库中，方便后续调用。


```