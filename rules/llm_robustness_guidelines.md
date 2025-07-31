# LLM 调用健壮性与可追溯性规范 (V1.0)

**所有**与大语言模型 (LLM) API 进行交互的模块，都**必须**遵守以下规范。本规范是代码审查 (Code Review) 的强制标准。

## 1. 核心原则

- **绝不信任外部服务**: 任何网络调用都可能失败，任何LLM的返回格式都可能偏离预期。代码必须能够优雅地处理这些异常，而不是崩溃。
- **一切皆可追溯**: 每一次调用都必须有据可查，便于调试、审计和性能分析。

## 2. 强制实施细则

### 2.1. 保留原始输出 (Raw Output Preservation)

在对LLM返回的任何数据进行解析或处理之前，其**未经修改的原始输出（无论是JSON字符串、文本还是其他格式）必须被完整记录**。

- **目的**:
    - **调试**: 当解析逻辑失败时，原始输出是定位问题的唯一依据。
    - **审计**: 允许事后分析LLM的实际表现，而非仅仅是我们解析后的结果。
    - **迭代**: 为未来优化Prompt或解析逻辑提供真实的样本。

### 2.2. 安全解析与分离 (Safe Parsing and Segregation)

所有对LLM返回结果的解析操作，都**必须**被包裹在 `try...except` 块中。

- **逻辑**:
    - `try` 块: 尝试解析LLM的返回内容，并将成功解析的数据对象传递给主业务流程。
    - `except` 块:
        - **必须**捕获所有可能的解析异常（如 `json.JSONDecodeError`, `KeyError`, `ValidationError` 等）。
        - **严禁**在 `except` 块中简单地 `pass` 或只打印一个简单的错误信息后就导致程序中断。
        - **必须**将解析失败的案例（包括但不限于：原始数据、错误信息、堆栈追踪）记录到一个专门的、可供人工审查的位置（例如，一个独立的 `llm_failures.jsonl` 日志文件或数据库中的一个特定表）。

### 2.3. 确保可追溯性 (Traceability)

每一次LLM调用及其对应的结果（无论成功或失败）都**必须**与一个唯一的关联ID绑定。

- **实现**:
    - 在发起LLM请求前，生成一个唯一的ID（例如，使用 `uuid.uuid4()`）。
    - 这个ID**必须**同时出现在：
        1. 发送给LLM的请求日志中。
        2. 记录成功解析结果的数据中。
        3. 记录解析失败案例的日志中。
- **目的**: 建立从“请求”到“原始输出”再到“最终结果（成功或失败）”的完整追踪链。

## 3. 伪代码示例

```python
import uuid
import json
from some_llm_client import call_llm

def process_text_with_llm(text_to_process: str):
    # 步骤 2.3: 生成唯一关联ID
    request_id = f"llm-req-{uuid.uuid4()}"
    
    try:
        # 调用LLM
        raw_output = call_llm(prompt=f"Process this: {text_to_process}")
        
        # 步骤 2.1: 记录原始输出
        log_raw_output(request_id, raw_output)
        
        # 步骤 2.2: 安全解析
        try:
            parsed_data = json.loads(raw_output)
            # ... 可能还有更复杂的Pydantic验证等
            
            # 处理成功解析的数据
            save_successful_result(request_id, parsed_data)
            return parsed_data
            
        except (json.JSONDecodeError, KeyError) as e:
            # 处理解析失败的案例
            log_parsing_failure(
                request_id=request_id,
                raw_output=raw_output,
                error_message=str(e)
            )
            return None

    except Exception as e:
        # 处理LLM调用本身的异常
        log_llm_call_failure(request_id, error_message=str(e))
        return None

```
