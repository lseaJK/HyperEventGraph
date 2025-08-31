# HyperEventGraph V3.1: LLM Prompt 优化指南

本文档旨在作为项目核心的“Prompt知识库”，详细说明系统中所有需要调用大语言模型（LLM）的场景。理解并优化这些Prompt是提升系统性能、降低成本和未来进行模型选型的关键。

---

## 核心原则

- **结构化输出**: 所有场景都强制要求LLM输出**纯净的、无任何解释性文本的JSON对象**。这是保证系统能够稳定解析和处理模型响应的基石。
- **任务分离**: `config.yaml` 文件将不同的任务（`triage`, `schema_generation`, `extraction`）路由到不同的模型。这允许我们为每个任务选择最适合（性价比最高）的模型。

---

## 场景1：批量初筛 (Batch Triage)

### 1.1. 调用目标 (Goal)

此场景的目标是**快速、低成本**地对海量原始文本进行初步分类。系统需要判断一段文本是描述了一个**已知的事件**、一个**未知的潜在事件**，还是**无关信息**，并给出一个置信度分数。

### 1.2. 核心提示词 (Core Prompt)

该提示词被设置为 `TriageAgent` 的系统消息。其中的 `{domains_str}` 和 `{event_types_str}` 被动态替换为当前系统中所有已知的领域和事件类型。

```
You are a Triage Agent responsible for classifying event types and their domains.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY a valid JSON object - nothing else.
2. DO NOT include any explanatory text before or after the JSON.
3. DO NOT use XML tags, markdown, or any other formatting.
4. DO NOT mention tools or function calls.

Your output format MUST be exactly:
{"status": "known", "domain": "事件领域", "event_type": "事件类型", "confidence": 0.95}

或者:
{"status": "unknown", "event_type": "Unknown", "domain": "unknown", "confidence": 0.99}}

IMPORTANT: If you output anything other than a pure JSON object, the system will fail.

Here are the domains you can recognize:
- {domains_str}

Here are the event types you can recognize:
- {event_types_str}

Analyze the provided text, determine the most appropriate domain and event type, and then output ONLY the JSON classification.
```

### 1.3. 预期输出 (Expected Output)

模型必须返回以下两种JSON结构之一：

- **当识别为已知事件时**:
  ```json
  {
    "status": "known",
    "domain": "financial",
    "event_type": "Company:MergerAndAcquisition",
    "confidence": 0.95
  }
  ```

- **当识别为未知或无关事件时**:
  ```json
  {
    "status": "unknown",
    "event_type": "Unknown",
    "domain": "unknown",
    "confidence": 0.99
  }
  ```

---

## 场景2：模式生成 (Schema Generation)

### 2.1. 调用目标 (Goal)

在人工审核员将一批相似的“未知事件”归类后，此场景的目标是利用LLM强大的归纳和推理能力，从这些文本样本中**自动生成一个结构化的JSON Schema**。

### 2.2. 核心提示词 (Core Prompt)

该提示词由 `SchemaLearningToolkit` 动态构建，其中的 `{sample_block}` 会被替换为一组相似的文本样本。

```
You are an expert data architect. Your task is to analyze text samples describing a specific event type and create a concise JSON schema.

**Instructions:**
1.  **Analyze Samples:** Understand the common theme.
2.  **Create Schema:** Generate a JSON object with "schema_name", "description", and "properties".
    -   `schema_name`: PascalCase:PascalCase format (e.g., "Company:ProductLaunch").
    -   `description`: A one-sentence explanation.
    -   `properties`: A dictionary of snake_case keys with brief descriptions.
3.  **Output:** Your entire output must be a single, valid JSON object.

**Text Samples:**
{sample_block}

**Example Output:**
{
  "schema_name": "Company:LeadershipChange",
  "description": "Describes the appointment or departure of a key executive.",
  "properties": {
    "company": "The company involved.",
    "executive_name": "The name of the executive.",
    "new_role": "The new position or title."
  }
}
```

### 2.3. 预期输出 (Expected Output)

模型必须返回一个描述新事件结构的JSON对象。

- **示例输出**:
  ```json
  {
    "schema_name": "Company:ProductLaunch",
    "description": "A new product is officially released to the market.",
    "properties": {
      "company": "The company launching the product.",
      "product_name": "The name of the new product.",
      "launch_date": "The official date of the launch."
    }
  }
  ```

---

## 场景3：事件抽取 (Event Extraction)

### 3.1. 调用目标 (Goal)

这是系统的核心价值实现环节。目标是根据一个**预先定义的JSON Schema**，从一段文本中**精确地抽取出所有对应的结构化信息**。

### 3.2. 核心提示词 (Core Prompt)

该提示词由 `PromptTemplateGenerator` 动态构建。它会将目标Schema (`{event_schema}`) 和原始文本 (`{text}`) 组合起来，并强制要求模型以JSON格式返回结果。

*(注：具体模板在 `src/event_extraction/prompt_templates.py` 中，以下为根据其逻辑生成的示例)*

```
You are an expert information extraction AI.
Your task is to extract structured data from the provided text based on the given JSON schema.

**CRITICAL INSTRUCTIONS:**
1.  Your output MUST be a single, valid JSON object that strictly conforms to the provided schema.
2.  Do NOT include any text or explanation before or after the JSON object.
3.  If a piece of information is not present in the text, omit the corresponding key or set its value to null.

**JSON Schema to follow:**
```json
{event_schema}
```

**Text to analyze:**
---
{text}
---

**Your JSON Output:**
```

### 3.3. 预期输出 (Expected Output)

模型必须返回一个**严格遵守输入Schema结构**的JSON对象。

- **输入Schema (示例)**:
  ```json
  {
    "title": "CompanyMergerAndAcquisition",
    "description": "Describes a merger or acquisition event between companies.",
    "type": "object",
    "properties": {
      "acquirer": { "type": "string", "description": "The company that is acquiring another." },
      "acquired": { "type": "string", "description": "The company that is being acquired." },
      "deal_amount": { "type": "number", "description": "The financial value of the deal." }
    }
  }
  ```

- **预期JSON输出 (示例)**:
  ```json
  {
    "acquirer": "腾讯控股有限公司",
    "acquired": "字节跳动旗下的TikTok业务",
    "deal_amount": 12000000000
  }
  ```

---

## 模型选型策略建议

- **初筛 (Triage)**: 此任务对成本和速度敏感，但对推理深度要求不高。适合选择**速度快、成本低**的小模型。
- **模式生成 (Schema Generation)**: 此任务需要强大的归纳、推理和创造力。适合选择**能力最强、上下文窗口最长**的旗舰模型。
- **事件抽取 (Extraction)**: 此任务需要极高的指令遵循能力、精确性和稳定的JSON输出能力。适合选择**经过严格指令微调**的高性能模型。
