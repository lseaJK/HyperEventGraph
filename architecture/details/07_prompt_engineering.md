# 技术文档 07: 提示词工程 (Prompt Engineering)

**关联章节**: [主架构文档第4章：核心技术与分析层](../HyperEventGraph_Architecture_V4.md#41-核心技术引擎)
**源目录**: `prompts/`

本篇文档将提示词（Prompts）作为一种特殊的“源代码”进行解析。在HyperEventGraph项目中，高质量、结构化的提示词是确保各个智能代理（Agents）能够稳定、可靠、精确地执行任务的基石。所有提示词都由 `PromptManager` 统一管理。

---

## 1. `triage.md` (初筛提示词)

-   **关联Agent**: `TriageAgent`
-   **设计理念**: **简洁、高效、强约束**。此提示词的目标是在最低成本下，让LLM做出一个快速的“二元+置信度”判断。
-   **关键构成**:
    -   **角色定义**: `You are a Triage Agent...`，明确告知LLM其当前身份。
    -   **绝对指令 (CRITICAL INSTRUCTIONS)**: 使用了一系列大写的、命令式的指令，如 `You MUST output ONLY a valid JSON object`，`DO NOT include any explanatory text`。这是为了最大限度地减少LLM输出“噪音”（如 "Here is the JSON you requested:"），确保输出可以直接被程序解析。
    -   **格式示例**: 提供了两个精确的、非此即彼的输出格式示例，让LLM对期望的输出结构有非常清晰的认识。
    -   **动态知识注入**: 包含了 `{domains_str}` 和 `{event_types_str}` 两个模板变量。`TriageAgent` 在运行时会用当前系统已知的所有领域和事件类型来填充它们，这使得提示词能够随着系统的学习而“进化”。
    -   **任务分割**: 使用 `--- TEXT TO ANALYZE ---` 和 `{text_sample}` 明确地将指令与待处理数据分开，结构清晰。

---

## 2. `extraction.md` (抽取提示词)

-   **关联Agent**: `ExtractionAgent`
-   **设计理念**: **Schema驱动、事实优先、零预测**。这是项目中最复杂的提示词之一，其核心是引导LLM严格遵循一个动态的JSON结构，并只抽��已发生的事实。
-   **关键构成**:
    -   **角色与领域定义**: `...specializing in the Semiconductor and related industries...`，为LLM设定了明确的领域背景。
    -   **核心任务**: `...extract one or more factual, occurred events...`，开宗明义，强调“事实”和“已发生”。
    -   **Schema表格化**: 将要抽取的JSON字段以Markdown表格的形式呈现，并对每个字段的含义、类型和可选值进行了详细说明，比直接展示一个JSON示例更易于LLM理解。
    -   **绝对禁止指令**: 使用了一个非���醒目的引用块（`> 🚫 **绝对禁止抽取预测类...**`）来强调整个系统最重要的原则之一：不处理预测和观点。这是保证知识库质量的生命线。
    -   **输出格式定义**: 提供了一个包含所有字段的、带注释的完整JSON结构，作为最终的格式参考。
    -   **示例驱动 (Few-shot Learning)**: 提供了一个高质量的“输入 -> 输出”示例 (`✅ 示例输入` -> `✅ 示例输出`)。这个示例不仅展示了正确的输出格式，更重要的是，它向LLM展示了如何处理包含预测信息的混合文本（即只抽取出其中的事实部分），这是一种非常有效的“行为示范”。
    -   **模板变量**: `{text_sample}` 用于在运行时注入待抽取的文本。

---

## 3. `relationship_analysis.md` (关系分析提示词)

-   **关联Agent**: `RelationshipAnalysisAgent`
-   **设计理念**: **上下文感知、逻辑严谨、可解释性**。此提示词旨在引导LLM进行更深层次的逻辑推理。
-   **关键构成**:
    -   **角色定义**: `作为一名情报分析师...`，赋予LLM一个需要进行思考和判断的角色。
    -   **上下文注入**: 包含了 `{context_summary}`, `{source_text}`, 和 `{event_descriptions}` 三个模板变量，分别对应知识库层、文档层和事件层的上���文，为LLM提供了最全面的决策信息。
    -   **严格的关系类型定义**: 不仅列出了所有合法的关系类型（`Causal`, `Temporal`等），更重要的是，**为每一种关系都提供了清晰、无歧义的定义和使用条件**。特别是对 `Causal` 和 `Temporal` 的严格限制，旨在避免LLM做出模糊或错误的判断。
    -   **可解释性要求**: 明确要求输出JSON中包含一个 `reason` 字段，`"解释你判断的理由"`。这迫使LLM对其推理过程进行“思考”，并为后续的人工审核和系统调试提供了极大的便利。
    -   **JSON输出格式示例**: 提供了一个清晰的、包含所有必需字段的JSON输出示例。

---

## 4. `schema_generation.md` (Schema生成提示词)

-   **关联Agent**: `SchemaLearnerAgent` (通过其工具包调用)
-   **设计理念**: **归纳推理、格式遵循**。此提示词的目标是让LLM扮演“数据架构师”的角色，从一批相似的文本样本中抽象和归纳出通用的数据结构。
-   **关键构成**:
    -   **角色定义**: `You are an expert data architect.`
    -   **简洁指令**: 采用了编号指令，清晰地列出了任务的三个步骤：分析样本、创建Schema、输出JSON。
    -   **命名规范**: 明确要求 `schema_name` 遵循 `PascalCase:PascalCase` 格式，`properties` 的键遵循 `snake_case` 格式，确保了系统内部Schema命名的一致性。
    -   **输出约束**: `Your entire output must be a single, valid JSON object.`，再次强调了对纯净JSON输出的要求。
    -   **模板变量**: `{sample_block}` 用于注入一批相似的事件描述文本。
    -   **示例驱动**: 提供了一个简单的输出示例，帮助LLM理解期望的最终产出结构。
