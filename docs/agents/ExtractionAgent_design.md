# ExtractionAgent - 技术设计文档

**版本**: 1.1 (AutoGen-based)
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位

**目标**: 对已确定为“已知类型”的事件文本，根据其精确的JSON Schema，进行深度、完整、结构化的信息抽取。

**定位**: `ExtractionAgent`是系统的“精加工车间”。它接收由`TriageAgent`分流来的“标准件”，并利用最强大的工具（强大的LLM和精确的Schema）进行精雕细琢，产出高质量的结构化数据。

**核心原则**: 深度与精度优先。

---

## 2. AutoGen框架集成

`ExtractionAgent` 将被实现为 `autogen.AssistantAgent` 的一个子类。其核心行为由两部分定义：
1.  **System Message**: 一个精心设计的系统提示词，告诉Agent它的角色是“事件抽取专家”。
2.  **Tools**: 一个或多个注册给Agent的Python函数。Agent不直接执行业务逻辑，而是通过调用其注册的工具来完成。

---

## 3. 类与工具定义

```python
# (伪代码)
import autogen
from some_config_loader import Config
from event_extraction_toolkit import EventExtractionToolkit # 这是一个代表现有逻辑的封装

class ExtractionAgent(autogen.AssistantAgent):
    """
    根据精确的Schema，对已知类型的事件进行深度信息抽取。
    """
    def __init__(self, llm_config: dict, config: Config):
        """
        :param llm_config: AutoGen格式的LLM配置。
        :param config: 全局应用配置。
        """
        super().__init__(
            name="ExtractionAgent",
            system_message="你是一个事件抽取专家。当被提供文本和事件类型时，你必须使用`extract_events_from_text`工具来抽取结构化信息。",
            llm_config=llm_config,
        )
        
        # 封装现有逻辑
        self.toolkit = EventExtractionToolkit(config)
        
        # 注册工具
        self.register_function(
            function_map={
                "extract_events_from_text": self.toolkit.extract_events_from_text
            }
        )
```

---

## 4. 工具核心逻辑 (`extract_events_from_text`)

这个函数封装了之前`.run()`方法的核心逻辑。

1.  **函数签名**: `def extract_events_from_text(self, text: str, event_type: str) -> list[dict]:`
2.  **获取Schema和Prompt**: 从`event_schemas.json`中加载指定`event_type`的完整Schema和对应的Prompt模板。
3.  **构建Prompt**: 将`text`和`JSON Schema`填入获取到的Prompt模板。
4.  **调用���大的LLM**: 通过`self.llm_client`执行查询。
5.  **解析并验证响应**: 使用`jsonschema`对LLM返回的JSON列表进行严格验证。
6.  **返回结果**: 返回通过验证的事件字典列表。
7.  **错误处理**: 捕获异常并返回带有错误信息的结果，或空列表。

---

## 5. 数据结构定义

(与V1.0相同，定义了工具的输入和输出)

### 5.1 工具输入

- `text: str`: 原始文本。
- `event_type: str`: 明确的事件类型，如 "企业收购"。

### 5.2 工具输出

- **成功**:
  ```json
  [
    {
      "id": "evt_uuid_1",
      "event_type": "企业收购",
      ...
    }
  ]
  ```
- **失败或未抽取到**: `[]` (空列表)

---

## 6. 与现有代码的映射关系

`ExtractionAgent`的重构核心是将**现有逻辑封装为Agent可调用的工具**。

- **`EventExtractionToolkit`**: 我们将创建一个新的类`EventExtractionToolkit`，它会整合`src/event_extraction`目录下的所有功能。
    - `deepseek_extractor.py` 和 `semiconductor_extractor.py` 的逻辑被封装进`toolkit.extract_events_from_text`方法。
    - `prompt_templates.py`, `schemas.py`, `validation.py`, `json_parser.py`的功能被这个toolkit在内部调用。
- **`ExtractionAgent`**: Agent本身变得很“薄”，它只负责理解任务（通过LLM��话）和调用正确的工具。

---

## 7. 依赖项

- **`autogen-agentchat`**: AutoGen核心框架。
- **PowerfulLLMClient**: 功能强大的LLM客户端。
- **Config**: 全局配置模块。
- **JSON Validator**: `jsonschema`库。
