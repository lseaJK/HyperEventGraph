# 技术文档 01: 核心基础设施

**关联章节**: [主架构文档第3章：数据处理与存储层](../HyperEventGraph_Architecture_V4.md#3-数据处理与存储层)
**源目录**: `src/core/`

本篇文档深入解析构成系统基石的核心基础设施模块。

---

## 1. 中央状态数据库管理器 (`database_manager.py`)

`DatabaseManager` 是与中央状态库 `master_state.db` 交互的唯一、统一的接口，确保了所有数据库操作的安全性和一致性。

### 1.1. 设计理念

-   **单一职责**: 该模块只负责数据库的CRUD（增删改查）操作，不包含任何业务逻辑。
-   **安全性**: 通过封装`sqlite3`的连接和游标管理，避免了SQL注入和连接泄漏的风险。
-   **健壮性**: 在初始化时会自动检查并添加新字段（如`story_id`），确保了数据库结构的向后兼容和系统的平滑升级。

### 1.2. 核心表结构 (`master_state`)

该模块管理的核心表结构定义了数据在系统中的完整生命周期。详细表结构请参见主架构文档 [3.1.1. 中央状态数据库 (SQLite)](../HyperEventGraph_Architecture_V4.md#311-中央状态数据库-sqlite)。

### 1.3. 关键方法解析

-   `_initialize_database()`:
    -   **触发时机**: 在`DatabaseManager`实例化时自动调用。
    -   **核心逻辑**:
        1.  执行 `CREATE TABLE IF NOT EXISTS master_state (...)` 来确保表的存在。
        2.  通过 `_add_column_if_not_exists()` 辅助方法，利用 `PRAGMA table_info(master_state)` 查询现有列，并**动态地** `ALTER TABLE ... ADD COLUMN ...` 来添加在后续开发中引入的新字段（如 `cluster_id`, `story_id`）。这是一个非常关键的健壮性设计。

-   `get_records_by_status_as_df(status: str) -> pd.DataFrame`:
    -   **功能**: 各个工作流用此方法来“认领”任务。
    -   **实现**: 使用`pandas.read_sql_query`，高效地将特定状态的所有记录作为DataFrame返回，便于上层进行批处理。

-   `update_record_after_triage(...)`:
    -   **功能**: 一个专用的更新方法，用于在初筛（Triage）后一次性更新多个字段（`current_status`, `assigned_event_type`, `triage_confidence`, `notes`）。
    -   **价值**: 提供了比通用`update`更清晰的业务意图。

-   `update_story_info(event_ids: list[str], ...)`:
    -   **功能**: 为属于同一个“故事”的一批事件，批量更新其`story_id`和`current_status`。
    -   **实现**: 采用 `WHERE id IN (...)` 的SQL语法，通过一次数据库调用高效地更新多���数据，避免了逐条更新的性能瓶颈。

---

## 2. 全局配置加载器 (`config_loader.py`)

`ConfigLoader` (在代码中通常通过 `load_config` 和 `get_config` 函数体现) 负责解析 `config.yaml` 文件，并将其内容作为全局可访问的配置对象。

### 2.1. 设计理念

-   **全局唯一**: 配置在程序启动时加载一次，之后在任何模块中都可以通过`get_config()`获取，保证了配置的一致性。
-   **解耦**: 将所有可变参数（如文件路径、模型名称、算法超参数）从代码中分离出来，使得调整系统行为无需修改代码。

### 2.2. 实现细节

-   **库**: 使用 `PyYAML` 库来安全地加载YAML文件。
-   **加载与获取**:
    -   `load_config(path)`: 在程序入口（如`main`函数）处调用，读取YAML文件并将其内容存储在一个全局变量中。
    -   `get_config()`: 在任何需要配置的模块中调用，返回已加载的配置字典。

---

## 3. 提示词管理器 (`prompt_manager.py`)

`PromptManager` 实现了提示词工程的核心原则：将提示词（Prompt）作为一种可配置的、与业务逻辑分离的资产进行管理。

### 3.1. 设计理念

-   **单例模式 (Singleton)**: 整个应用程序中只存在一个`PromptManager`实例 (`prompt_manager`)。这确保了提示词��板只需从磁盘加载一次，提高了性能并节约了内存。
-   **模板化**: 将提示词存储在独立的 `.md` 文件中，并使用Python的字符串格式化占位符（如 `{text_sample}`）。

### 3.2. 实现细节

-   `__init__(self, prompt_dir: str = "prompts")`:
    -   构造函数只在第一次实例化时执行初始化逻辑。
    -   它会自动计算出项目根目录下的 `prompts` 文件夹路径，使其不受当前工作目录的影响。

-   `_load_template(self, template_name: str) -> str`:
    -   一个私有方法，负责从磁盘读取模板文件。
    -   **内置缓存**: 它使用一个实例字典 `self.template_cache` 来缓存已加载的模板。当第二次请求同一个模板时，会直接从内存缓存中返回，避免了不必要的磁盘I/O。

-   `get_prompt(self, template_name: str, **kwargs: Any) -> str`:
    -   这是外部模块调用的主要接口。
    -   它首先确保模板已加载（通过 `_load_template`），然后使用传入的关键字参数（`**kwargs`）来填充模板中的占位符。
    -   包含错误处理，如果传入的参数与模板中的占位符不匹配，会抛出`ValueError`。
