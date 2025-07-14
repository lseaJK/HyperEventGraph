# TriageAgent - 技术设计文档

**版本**: 1.1 (AutoGen-based)
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位

**目标**: 快速、低成本地对输入的任意文本进行“分诊”，判断其核心内容是否属于任何一个系统已知的事件类型。

**定位**: `TriageAgent`是整个实时处理工作流的“看门人”和“交通警察”。它位于流程的最前端，负责将流量导向正确的处理路径（深度抽取 or 存入未知事件池），从而避免将昂贵的计算资源浪费在无法处理或不相关的文本上。

**核心原则**: 速度优先，成本敏感。

---

## 2. AutoGen框架集成

`TriageAgent` 将被实现为 `autogen.AssistantAgent` 的一个子类。

- **System Message**: "你是一个事件分类专家。你的任务是判断用户提供的文本属于哪个已知的事件类型。如果都不属于，就判断为未知。你必须使用`classify_event_type`工具来完成任务。"
- **Tools**: 分诊的核心逻辑将被封装成一个Agent可调用的工具。

---

## 3. 类与工具定义

```python
# (伪代码)
import autogen
from some_config_loader import Config
from triage_toolkit import TriageToolkit # 这是一个代表现有逻辑的封装

class TriageAgent(autogen.AssistantAgent):
    """
    负责对输入文本进行快速事件类型分类。
    """
    def __init__(self, llm_config: dict, config: Config):
        """
        :param llm_config: AutoGen格式的LLM配置 (应配置为使用轻量级模型)。
        :param config: 全局应用配置。
        """
        super().__init__(
            name="TriageAgent",
            system_message="你是一个事件分类专家...",
            llm_config=llm_config,
        )
        
        self.toolkit = TriageToolkit(config)
        
        self.register_function(
            function_map={
                "classify_event_type": self.toolkit.classify_event_type
            }
        )
```

---

## 4. 工具核心逻辑 (`classify_event_type`)

1.  **函数签名**: `def classify_event_type(self, text: str) -> dict:`
2.  **加载已知类型**: 从`event_schemas.json`加载事件类型和描述，格式化为字符串列表。
3.  **构建Prompt**: 将类型列表和输入的`text`填入为分诊任务专门设计的Prompt模板。
4.  **调用轻量级LLM**: 通过`self.llm_client`执行查询。
5.  **解析响应**: 解析LLM返回的`{"decision": "known" | "unknown", "type": "..."}`。
6.  **处理"已知"情况**: 如果是`"known"`，返回包含状态和类型的字典。
7.  **处理"未知"情况**: 如果是`"unknown"`，调用内部方法`_log_unknown_event`将事件写入`.jsonl`文件，然后返回包含状态和建议类型的字典。
8.  **返回结果**: 返回一个包含分诊结果的字典，这个字典将作为工具调用的结果在Agent之间传递。

---

## 5. 数据结构定义

(与V1.0相同，定义了工具的输入和输出)

### 5.1 工具输入
- `text: str`: 原始文本。

### 5.2 工具输出
- **成功 (已知)**: `{"status": "known", "event_type": "企业收购", ...}`
- **成功 (未知)**: `{"status": "unknown", "proposed_type": "新产品发布"}`
- **失败**: `{"status": "error", "message": "..."}`

---

## 6. 与现有代码的映射关系

`TriageAgent`的实现核心是创建一个新的`TriageToolkit`类，该类复用现有基础设施。

- **`TriageToolkit`**:
    - `classify_event_type`方法是新开发的核心逻辑，主要负责Prompt工程和LLM调用。
    - **LLM客户端**: 复用`src/event_extraction/deepseek_extractor.py`的调用逻辑，但配置为轻量级模型。
    - **Schema加载**: 复用`src/event_extraction/schemas.py`的逻辑。
    - **日志记录**: `_log_unknown_event`方法复用`src/output/jsonl_manager.py`的逻辑。

---

## 7. 依赖项

- **`autogen-agentchat`**: AutoGen核心框架。
- **LightweightLLMClient**: 轻量级LLM客户端。
- **Config**: 全局配置模块。
- **JSON Parser**: 用于解析LLM响应。
