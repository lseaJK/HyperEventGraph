# 异步事件抽取工作流操作指南

## 1. 简介

这是一个异步的、可中断的、有人类在回路（Human-in-the-Loop）的事件抽取工作流。它允许您提交一个包含文本的JSON文件进行分析，并在AI处理的关键阶段（事件分类、事件抽取）暂停，等待您的审核和确认，然后再继续执行。

这种设计使您无需实时在线等待AI处理完成，可以按照自己的节奏参与和指导整个流程。

## 2. 核心文件

工作流通过以下三个文件与您交互和管理状态：

-   `workflow_state.json`: **工作流的“存档”文件**。它记录了当前任务进行到了哪一步，以及到目前为止的所有产出。**您通常不需要手动编辑此文件。**
-   `review_request.txt`: **给您的“任务单”**。当工作流需要您的审核或输入时，会生成或更新此文件，其中包含清晰的指示和AI的处理结果。
-   `review_response.txt`: **您给AI的“回复”**。您需要创建并编辑此文件来响应`review_request.txt`中的任务，然后再次运行工作流。

## 3. 快速开始：运行一个完整的流程

### 第1步：准备输入文件

创建一个JSON文件（例如 `my_input.json`），其中必须包含一个`"text"`字段，值为您想分析的新闻文本。

**示例 `my_input.json`:**
```json
{
  "text": "2024年7月15日，科技巨头A公司正式宣布，将以惊人的500亿美元全现金方式收购新兴AI芯片设计公司B公司。此次收购旨在强化A公司在人工智能领域的硬件布局。"
}
```

### 第2步：启动工作流

在您的终端中，确保您位于项目根目录 (`E:\HyperEventGraph`)，然后运行以下命令：

```bash
python run_async_workflow.py --input my_input.json
```

-   `--input` 参数告诉控制器启动一个**新**的工作流。
-   程序将执行**事件分流（Triage）**阶段，然后暂停。
-   执行完毕后，会自动生成 `review_request.txt`。

### 第3步：审核事件分类

-   打开新生成的 `review_request.txt` 文件。内容会类似这样：

    ```
    --- Triage Review Request ---
    The AI has classified the event in the text with the following details:
    - Domain: financial
    - Event Type: company_merger_and_acquisition
    --- Actions ---
    ...
    ```

-   **创建**一个名为 `review_response.txt` 的新文件。
-   根据您的判断，在 `review_response.txt` 中写入您的回复。

    -   **如果分类正确**，写入：
        ```
        status: CONFIRMED
        ```
    -   **如果分类错误**，您可以直接修正。例如：
        ```json
        {
           "domain": "financial",
           "event_type": "investment_and_financing"
        }
        ```

### 第4步：继续工作流（执行抽取）

-   保存 `review_response.txt` 文件后，**不带任何参数**再次运行控制器：

    ```bash
    python run_async_workflow.py
    ```

-   控制器会读取您的回复，更新状态，然后执行**事件抽取（Extraction）**阶段。
-   执行完毕后，`review_request.txt` 会被**新的内容覆盖**，要求您审核抽取出的具体事件。

### 第5步：审核抽取结果

-   再次打开 `review_request.txt`。内容会类似这样：

    ```
    --- Extraction Review Request ---
    The AI has extracted the following event(s). Please review, correct, or add information as needed.
    --- Extracted Data ---
    [
      {
        "source": "my_input.json",
        "publish_date": "2025-01-01",
        "event_type": "公司并购",
        "acquirer": "A公司",
        "acquired": "B公司",
        ...
      }
    ]
    --- End of Data ---
    ...
    ```

-   打开 `review_response.txt`（它在上一部已被自动删除，您需要重新创建）。

    -   **��果抽取结果完全正确**，写入：
        ```
        status: CONFIRMED
        ```
    -   **如果需要修正或补充**，将 `review_request.txt` 中的 `--- Extracted Data ---` 部分的JSON数组**复制**到 `review_response.txt` 中，然后直接编辑。例如，修正交易金额：
        ```json
        [
          {
            "source": "my_input.json",
            "publish_date": "2025-01-01",
            "event_type": "公司并购",
            "acquirer": "科技巨头A公司",
            "acquired": "新兴AI芯片设计公司B公司",
            "deal_amount": 5000000.0,
            ...
          }
        ]
        ```

### 第6步：完成工作流

-   保存 `review_response.txt` 后，**再次不带参数**运行控制器：

    ```bash
    python run_async_workflow.py
    ```

-   控制器会读取您最终确认的数据，执行**关系分析和存储**，并将工作流标记为“完成”。
-   所有临时文件会被清理，最终结果会保存在项目中（当前版本的 `StorageAgent` 只是打印到控制台，未来可以保存到文件或数据库）。

您已成功完成一次异步人机协作的事件抽取！
