# HyperEventGraph 项目总规则

## 1. 流程规范
- 高层规划 → 拆解小项 → 写 TODO → 分批执行 → 更新 TODO 并同步至 architecture.md → 阶段性反馈 → 最终收尾

## 2. 文档分离原则
- **架构文档** (`architecture.md`): 保持简洁，专注于整体架构设计和技术路径
- **标准规范** (`hypergraph_standards.md`): 详细的格式规范、标准定义和示例
- **任务管理** (`todo.md`): 阶段性任务列表和开发计划
- **项目规则** (`project_rules.md`): 项目管理和文档组织规范
- **避免在多个文档中重复详细内容，使用文件引用的方式链接相关规范**

## 3. TODO 管理
- 小项格式：`- [ ] 子任务描述`  
- 完成后打勾 `- [x]`，在阶段反馈中说明，并将其归档到 `/rules/architecture.md`
- 任务按阶段分组，每个阶段有明确的目标和可交付成果

## 4. 单元测试
- 覆盖正常、边界、异常场景  
- 新增功能时必须对应新增 `tests/test_*.py`
- 测试驱动开发 (TDD)：先写测试，再实现功能

## 5. 提交规范
- feat: 添加子任务 XXX 实现及测试  
- fix: 修复子任务 XXX 异常  
- docs: 更新 `/rules` 下相应文档
- refactor: 代码重构
- chore: 构建过程或辅助工具的变动

## 6. 文档存放
- `/rules/todo.md`：任务拆解与状态
- `/rules/architecture.md`：规划与决策
- `/rules/project_rules.md`：规则总览
- `/rules/hypergraph_standards.md`：知识图谱标准规范
- `/docs/`：项目文档和补充材料

## 7. 目录结构说明
- `/src/`: 源代码模块
- `/tests/`: 测试代码
- `/data/`: 数据文件
- `/docs/`: 项目文档
- `/rules/`: 项目规则和规范
- `/materials/`: 存放项目附加的程序，需要同步到github但是在项目构建时可以不用考虑

## 8. 代码质量标准
- 遵循 PEP 8 Python 代码规范
- 函数和类必须有文档字符串
- 使用类型提示 (Type Hints)
- 复杂逻辑必须有注释说明

## 特别说明
- 总是用中文回复
- 保持文档简洁，避免冗余
- 重要的格式规范单独成文件