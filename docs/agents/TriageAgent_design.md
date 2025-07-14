# TriageAgent - 技术设计文档

**版本**: 1.0
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位 (Goal & Positioning)

**目标**: 快速、低成本地对输入的任意文本进行“分诊”，判断其核心内容是否属于任何一个系统已知的事件类型。

**定位**: `TriageAgent`是整个实时处理工作流的“看门人”和“交通警察”。它位于流程的最前端，负责将流量导向正确的处理路径（深度抽取 or 存入未知事件池），从而避免将昂贵的计算资源（如功能强大的LLM）浪费在无法处理或不相关的文本上。

**核心原则**: 速度优先，成本敏感。

---

## 2. 类与方法定义

```python
# (伪代码)
from some_llm_client import LightweightLLMClient
from some_config_loader import Config

class TriageAgent:
    """
    负责对输入文本进行快速事件类型分类。
    """
    def __init__(self, llm_client: LightweightLLMClient, config: Config):
        """
        通过依赖注入初始化Agent。
        
        :param llm_client: 一个轻量级、快速的LLM客户端实例。
        :param config: 全局配置对象，用于获取prompt模板路径、已知schema等。
        """
        self.llm_client = llm_client
        self.config = config
        self.prompt_template = self._load_prompt_template()
        self.known_event_types = self._load_known_event_types()

    def run(self, text: str) -> dict:
        """
        执行分诊的核心方法。
        
        :param text: 待处理的原始文本。
        :return: 一个包含分诊结果的字典。
        """
        # ... 详细逻辑见下方 ...
        pass

    def _load_prompt_template(self) -> str:
        """从配置文件指定的路径加载Prompt模板。"""
        # ... 实现 ...
        pass

    def _load_known_event_types(self) -> list[dict]:
        """从event_schemas.json加载所有已知事件的类型和描述。"""
        # ... 实现 ...
        pass
    
    def _log_unknown_event(self, proposed_type: str, text: str):
        """将未知事件记录到pending_new_types.jsonl文件中。"""
        # ... 实现 ...
        pass
```

---

## 3. `.run()` 方法核心逻辑

1.  **格式化已知类型**: 将`self.known_event_types`格式化为一个易于LLM理解的字符串列表。
    ```
    # 示例
    event_type_list_str = ' - "企业收购": 描述一家公司对另一家公司的收购或合并行为。\n - "高管变动": 描述公司重要管理人员的任命、离职或退休。'
    ```

2.  **构建Prompt**: 将上一步的列表和输入的`text`填入`self.prompt_template`。

3.  **调用LLM**:
    ```python
    llm_response = self.llm_client.query(prompt)
    ```

4.  **解析响应**: 对LLM返回的（可能是JSON格式的）字符串进行解析。
    *   **预期格式**: `{"decision": "known" | "unknown", "type": "事件类型名"}`
    *   需要有健壮的解析逻辑，能处理轻微的格式偏差。

5.  **处理"已知"情况**:
    *   如果`decision`是`"known"`，并且`type`在`self.known_event_types`的名称列表中。
    *   返回结果: `{"status": "known", "event_type": type, "source_text": text}`

6.  **处理"未知"情况**:
    *   如果`decision`是`"unknown"`。
    *   调用`self._log_unknown_event(proposed_type=type, text=text)`将该事件记录到日志文件。
    *   返回结果: `{"status": "unknown", "proposed_type": type}`

7.  **错误处理**:
    *   如果LLM调用失败，记录错误并返回 `{"status": "error", "message": "LLM call failed."}`。
    *   如果响应解析失败，记录错误和原始响应，并返回 `{"status": "error", "message": "Failed to parse LLM response."}`。

---

## 4. 数据结构定义

### 4.1 输入

- `text: str`: 原始文本。

### 4.2 输出

- **成功 (已知)**:
  ```json
  {
    "status": "known",
    "event_type": "企业收购", // LLM判断出的已知类型
    "source_text": "..." // 原始文本
  }
  ```
- **成功 (未知)**:
  ```json
  {
    "status": "unknown",
    "proposed_type": "新产品发布" // LLM建议的新类型
  }
  ```
- **失败**:
  ```json
  {
    "status": "error",
    "message": "具体的错误信息"
  }
  ```

### 4.3 `pending_new_types.jsonl` 文件条目

```json
{
  "proposed_type": "新产品发布",
  "source_text": "...",
  "timestamp": "2025-07-14T12:00:00Z",
  "status": "pending",
  "cluster_id": null
}
```

---

## 5. 与现有代码的映射关系

`TriageAgent` 是一个新的功能概念，在现有代码库中没有直接对应的模块。它的实现将是创建新代码，但可以复用大量现有基础设施。

- **LLM 客户端**: 可以复用或借鉴 `src/event_extraction/deepseek_extractor.py` 中已经实现的LLM调用逻辑，但需要将其配置为使用一个更轻量级、响应更快的模型，以符合其“快速分诊”的定位。
- **配置管理**: 将复用项目已有的配置加载机制（可能在 `src/config/` 下），用于获取Prompt模板路径、已知Schema文件路径等。
- **Schema 加载**: `_load_known_event_types` 方法可以复用 `src/event_extraction/schemas.py` 中的逻辑来读取 `event_schemas.json` 文件，但只加载 `event_type` 和 `description` 字段，以保持轻量。
- **日志记录**: `_log_unknown_event` 方法在向 `.jsonl` 文件写入未知事件时，可以复用 `src/output/jsonl_manager.py` 中已经存在的逻辑。

`TriageAgent` 的价值在于引入了“分流”这一新能力，它的实现重点是新开发的Prompt工程和对现有基础组件的巧妙复用。

---

## 6. 依赖项

- **LightweightLLMClient**: 一个实现了`.query(prompt)`方法的LLM客户端，配置为使用快速、低成本的模型。
- **Config**: 全局配置模块，提供`event_schemas.json`和`pending_new_types.jsonl`的文件路径。
- **JSON Parser**: 用于解析LLM响应。