# 项目总规则

## 1. 流程规范
- 高层规划 → 拆解小项 → 写 TODO → 分批执行 → 更新 TODO 并同步至 architecture.md → 阶段性反馈 → 最终收尾

## 2. TODO 管理
- 小项格式：`- [ ] 子任务描述`  
- 完成后打勾 `- [x]`，在阶段反馈中说明，并将其归档到 `/rules/architecture.md`

## 3. 单元测试
- 覆盖正常、边界、异常场景  
- 新增功能时必须对应新增 `tests/test_*.py`

## 4. 提交规范
- feat: 添加子任务 XXX 实现及测试  
- fix: 修复子任务 XXX 异常  
- docs: 更新 `/rules` 下相应文档

## 5. 文档存放
- `/rules/todo.md`：任务拆解与状态  
- `/rules/architecture.md`：规划与决策  
- `/rules/project_rules.md`：规则总览

## 5. 文档存放
- `/rules/todo.md`：任务拆解与状态
- `/rules/architecture.md`：规划与决策
- `/rules/project_rules.md`：规则总览

## 6. 目录结构说明
- `/materials`: 存放项目附加的程序，需要同步到github但是在项目构建时可以不用考虑。

## 特别说明
- 总是用中文回复