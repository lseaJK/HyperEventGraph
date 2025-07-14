# ExtractionAgent - 技术设计文档

**版本**: 1.0
**作者**: Gemini Architect
**日期**: 2025-07-14

---

## 1. 目标与定位

**目标**: 对已确定为“已知类型”的事件文本，根据其精确的JSON Schema，进行深度、完整、结构化的信息抽取。

**定位**: `ExtractionAgent`是系统的“精加工车间”。它接收由`TriageAgent`分流来的“标准件”，并利用最强大的工具（强大的LLM和精确的Schema）进行精雕细琢，产出高质量的结构化数据。

**核心原则**: 深度与精度优先。

---

## 2. 类与方法定义

```python
# (伪代码)
from some_llm_client import PowerfulLLMClient
from some_config_loader import Config

class ExtractionAgent:
    """
    根据精确的Schema，对已知类型的事件进行深度信息抽取。
    """
    def __init__(self, llm_client: PowerfulLLMClient, config: Config):
        """
        :param llm_client: 一个功能强大的LLM客户端实例。
        :param config: 全局配置对象。
        """
        self.llm_client = llm_client
        self.config = config
        self.all_schemas = self._load_all_schemas()

    def run(self, text: str, event_type: str) -> list[dict]:
        """
        执行深度抽取的核心方法。
        
        :param text: 待处理的原始文本。
        :param event_type: 由TriageAgent确定的已知事件类型。
        :return: 一个包含所有抽取出的事件字典的列表。
        """
        # ... 详细逻辑见下方 ...
        pass

    def _load_all_schemas(self) -> dict:
        """从event_schemas.json加载所有事件的完整Schema。"""
        # ... 实现 ...
        pass
    
    def _get_schema_and_prompt(self, event_type: str) -> (dict, str):
        """根据event_type获取其对应的schema和prompt模板。"""
        # ... 实现 ...
        pass
```

---

## 3. `.run()` 方法核心逻辑

1.  **获取Schema和Prompt**: 调用 `self._get_schema_and_prompt(event_type)`，获取当前事件类型对应的JSON Schema和为该类型优化过的Prompt模板。如果找不到，记录错误并返回空列表。

2.  **构建Prompt**: 将`text`和`JSON Schema`填入获取到的Prompt模板。Prompt需要明确指示LLM严格按照给定的Schema格式和字段要求进行输出。

3.  **调用强大的LLM**:
    ```python
    llm_response = self.llm_client.query(prompt)
    ```

4.  **解析并验证响应**:
    *   使用健壮的JSON解析器解析LLM的响应。由于可能在一篇文本中发现多个同类型事件，预期LLM返回一个JSON列表 `[{}, {}]`。
    *   对列表中的每一个JSON对象，使用其对应的JSON Schema进行严格的结构和类型验证。
    *   验证失败的对象将被丢弃或记录到错误日志中。

5.  **返回结果**: 返回一个只包含通过了Schema验证的事件字典的列表 `list[dict]`。

6.  **错误处理**:
    *   LLM调用失败: 记录错误，返回空列表 `[]`。
    *   JSON解析失败: 记录错误和原始响应，返回空列表 `[]`。
    *   Schema验证失败: 记录哪些字段验证失败，不将该事件包含在最终返回结果中。

---

## 4. 数据结构定义

### 4.1 输入

- `text: str`: 原始文本。
- `event_type: str`: 明确的事件类型，如 "企业收购"。

### 4.2 输出

- **成功**:
  ```json
  [
    {
      "id": "evt_uuid_1",
      "event_type": "企业收购",
      "participants": ["收购方A", "被收购方B"],
      "properties": {"amount": "1亿美金", "status": "已完成"},
      "confidence": 0.95,
      "source_text": "文本片段..."
    }
  ]
  ```
- **失败或未抽取到**: `[]` (空列表)

---

## 5. 与现有代码的映射关系

`ExtractionAgent` 的核心功能是现有 `src/event_extraction` 模块的直接演进和封装。重构时应最大程度地复用以下组件：

- **核心抽取逻辑**: `.run()` 方法的主要逻辑应重构自 `src/event_extraction/deepseek_extractor.py` 和 `src/event_extraction/semiconductor_extractor.py` 中的抽取流程。这包括LLM的调用、重试机制和响应处理。
- **LLM客户端**: 应直接复用 `src/event_extraction/deepseek_extractor.py` 中已实现的 `DeepSeekEventExtractor` 类或其底层的LLM API调用方式。
- **Prompt管理**: Prompt的加载和格式化逻辑应复用 `src/event_extraction/prompt_templates.py`。
- **Schema管理**:
    - Schema的加载逻辑应复用 `src/event_extraction/schemas.py`。
    - Schema的验证逻辑应复用 `src/event_extraction/validation.py`。
- **JSON解析**: 应复用 `src/event_extraction/json_parser.py` 中的健壮解析功能。

通过这种方式，`ExtractionAgent` 将成为一个更高层次的编排器，它封装和调用了 `src/event_extraction` 中已经过测试的、成熟的子组件。

---

## 6. 依赖项

- **PowerfulLLMClient**: 一个实现了`.query(prompt)`方法的LLM客户端，配置为使用功能强大的模型（如GPT-4, Gemini 1.5 Pro）。
- **Config**: 全局配置模块，提供`event_schemas.json`和各事件Prompt模板的路径。
- **JSON Validator**: 一个能够根据JSON Schema验证JSON对象的库（如 `jsonschema`）。