# HyperEventGraph V3.1: 端到端实验指南

本文档指导您完成一个完整的端到端实验，以验证和体验V3.1架构的全流程。

---

## 实验前准备

请确保您已经完成了以下步骤：
1.  成功安装所有在 `requirements.txt` 中定义的依赖。
2.  在您的运行环境中正确设置了所需的大模型API密钥（例如 `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`）。
3.  **（首次实验）注入初始数据**：如果您是第一次运行实验或希望从一个干净的数据库开始，请先运行以下脚本。它会读取 `IC_data/filtered_data.json` 的内容，并将其存入数据库，状态均为 `pending_triage`。
    ```bash
    python temp_seed_data.py
    ```

---

## 实验步骤

请严格按照以下顺序执行命令，以模拟数据在系统中的完整生命周期。

### 第1步：批量初筛

此脚本会读取数据库中所有 `pending_triage` 状态的数据，使用TriageAgent进行分类，并将结果（事件类型、置信度）写回数据库，状态更新为 `pending_review`。

```bash
python run_batch_triage.py
```

### 第2步：准备人工审核文件

上一步完成后，运行此脚本。它会从数据库中提取所有待审核的条目，并生成一个 `review_sheet.csv` 文件。文件内容会根据AI的置信度升序排列，以便您优先处理最不确定的案例。

```bash
python prepare_review_file.py
```

### ��3步：人工审核 (您的操作)

这是将您的领域知识注入系统的关键一步。

1.  在项目根目录找到并打开 `review_sheet.csv` 文件。
2.  **逐行检查**，并根据您的专业判断，修改以下两列：
    *   `human_decision`: 如果您认为这是一个已知的、有价值的事件，请修改为 `known`。如果您认为这是一个新的、需要学习的事件类型，请保持 `unknown`。
    *   `human_event_type`: 如果您将 `human_decision` 设为 `known`，请在这一列准确填写该事件对应的Schema名称（例如 `Company:Financials`）。
3.  保存并关闭CSV文件。

### 第4步：处理审核结果

当您保存了修改后的CSV文件后，运行此脚本。它会读取您的审核结果，并将这些经过校准的权威信息更新回中央数据库。

```bash
python process_review_results.py
```

### 第5步：知识循环：学习与抽取

根据您在第3步的决定，数据现在已经被分别流转到了“学习”或“抽取”两个不同的流程中。

*   **对于需要学习的数据 (`pending_learning`)**:
    运行交互式学习工作流。您可以通过命令行与系统互动，对新事件进行聚类、归纳并生成新的Schema。
    ```bash
    python run_learning_workflow.py
    ```

*   **对于需要抽取的数据 (`pending_extraction`)**:
    运行批量抽取工作流，将高质量的已知事件转化为最终的结构化知识。
    ```bash
    python run_extraction_workflow.py
    ```

---
实验完成。通过以上步骤，您已经完整地体验了数据流入、AI初筛、人工校准、系统学习/抽取的闭环过程。