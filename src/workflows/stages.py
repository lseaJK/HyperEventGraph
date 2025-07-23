# src/workflows/stages.py

import json
from pathlib import Path
from typing import Dict, Any

from src.agents.triage_agent import TriageAgent
from src.agents.relationship_analysis_agent import RelationshipAnalysisAgent
from src.agents.storage_agent import StorageAgent
from src.event_extraction.deepseek_extractor import DeepSeekEventExtractor
from src.event_extraction.schemas import get_event_model

# (其他Agent和工具的导入将在这里添加)

# --- Agent LLM 配置 (需要从外部传入或从配置文件加载) ---
# 这是一个示例，实际应用中需要更灵活的配置方式
LLM_CONFIG_KIMI = {
    "config_list": [{
        "model": "moonshot-v1-8k",
        "api_key": "YOUR_SILICON_API_KEY", # 需要替换
        "base_url": "https://api.siliconflow.cn/v1"
    }],
    "temperature": 0.0
}
# 同样为DeepSeek创建一个示例配置
LLM_CONFIG_DEEPSEEK = {
    "config_list": [{
        "model": "deepseek-chat",
        "api_key": "YOUR_DEEPSEEK_API_KEY", # 需要替换
        "base_url": "https://api.deepseek.com/v1"
    }],
    "temperature": 0.0
}


# --- 审核文件 ---
REVIEW_REQUEST_FILE = Path("review_request.txt")

# --- 阶段实现 ---

async def execute_triage_stage(state: WorkflowState, state_manager: StateManager) -> WorkflowState:
    """
    执行事件分流，并将结果写入状态和审核文件。
    """
    print("--- Executing Triage Stage ---")
    
    # 1. 从输入文件加载文本
    try:
        with open(state.input_file, 'r', encoding='utf-8') as f:
            # 假设输入是JSON，且文本在'text'字段中
            input_data = json.load(f)
            text_to_analyze = input_data.get("text")
            if not text_to_analyze:
                raise ValueError("Input JSON must have a 'text' field.")
        state.original_text = text_to_analyze
    except Exception as e:
        print(f"Error reading or parsing input file: {e}")
        return state_manager.update_state(state, new_stage="failed", error_message=str(e))

    # 2. 初始化并运行 TriageAgent
    try:
        triage_agent = TriageAgent(llm_config=LLM_CONFIG_KIMI)
        # Autogen agents are not async by default, running in executor
        response = await asyncio.to_thread(
            triage_agent.generate_reply,
            messages=[{"role": "user", "content": text_to_analyze}]
        )
        
        # 假设Agent直接返回JSON字符串
        triage_data = json.loads(response)
        triage_result = TriageResult(**triage_data)
        
    except Exception as e:
        print(f"Error during triage execution: {e}")
        return state_manager.update_state(state, new_stage="failed", error_message=f"Triage failed: {e}")

    # 3. 生成审核请求
    review_content = f"""--- Triage Review Request ---

Workflow ID: {state.workflow_id}
Input File: {state.input_file}

The AI has classified the event in the text with the following details:
- Domain: {triage_result.domain}
- Event Type: {triage_result.event_type}

--- Actions ---

1. To CONFIRM this classification and proceed to the extraction stage,
   create a file named 'review_response.txt' with the following content:
   
   status: CONFIRMED

2. To REJECT this classification and stop the workflow,
   create 'review_response.txt' with:
   
   status: REJECTED

3. To CORRECT the classification, create 'review_response.txt' with the
   corrected data in JSON format:

   {{
       "domain": "your_corrected_domain",
       "event_type": "your_corrected_event_type"
   }}

Please provide your response and run the workflow again.
"""
    with open(REVIEW_REQUEST_FILE, 'w', encoding='utf-8') as f:
        f.write(review_content)
    
    print(f"Triage complete. Review request written to '{REVIEW_REQUEST_FILE.name}'.")
    
    # 4. 更新状态并保存
    return state_manager.update_state(
        state,
        new_stage="awaiting_triage_review",
        original_text=text_to_analyze,
        triage_result=triage_result
    )

async def execute_extraction_stage(state: WorkflowState, state_manager: StateManager) -> WorkflowState:
    """
    根据已确认的事件类型，执行事件抽取。
    """
    print("--- Executing Extraction Stage ---")

    # 1. 获取事件模型
    event_type = state.triage_result.event_type
    event_model = get_event_model(event_type)
    if not event_model:
        error_msg = f"Extraction failed: Could not find a Pydantic model for event type '{event_type}'."
        print(error_msg)
        return state_manager.update_state(state, new_stage="failed", error_message=error_msg)

    # 2. 初始化抽取器并执行抽取
    try:
        # 注意：这里的配置需要被正确管理，例如通过一个中心化的配置模块
        extractor = DeepSeekEventExtractor() # 使用默认配置
        extracted_event = await extractor.extract(
            text=state.original_text,
            event_model=event_model,
            metadata={"source": state.input_file, "publish_date": "2025-01-01"} # 日期需要从文本或元数据中获取
        )
        
        if not extracted_event:
            error_msg = "Extractor returned no event."
            print(error_msg)
            # 即使没抽取出东西，也进入审核阶段，让用户可以手动添加
            extracted_events_dict = []
        else:
            extracted_events_dict = [extracted_event.model_dump(mode='json')]

    except Exception as e:
        print(f"Error during extraction: {e}")
        return state_manager.update_state(state, new_stage="failed", error_message=f"Extraction failed: {e}")

    # 3. 生成审核请求
    review_content = f"""--- Extraction Review Request ---

Workflow ID: {state.workflow_id}
Event Type: {event_type}

The AI has extracted the following event(s). Please review, correct, or add information as needed.

--- Extracted Data ---
{json.dumps(extracted_events_dict, indent=2, ensure_ascii=False)}
--- End of Data ---

--- Actions ---

1. To CONFIRM the extracted data and proceed to the finalization stage,
   create a file named 'review_response.txt' with the following content:
   
   status: CONFIRMED

2. To CORRECT the data, copy the JSON block above into 'review_response.txt',
   make your changes, and save the file.

Please provide your response and run the workflow again.
"""
    with open(REVIEW_REQUEST_FILE, 'w', encoding='utf-8') as f:
        f.write(review_content)

    print(f"Extraction complete. Review request written to '{REVIEW_REQUEST_FILE.name}'.")

    # 4. 更新状态并保存
    return state_manager.update_state(
        state,
        new_stage="awaiting_extraction_review",
        extracted_events=extracted_events_dict
    )

async def execute_finalization_stage(state: WorkflowState, state_manager: StateManager) -> WorkflowState:
    """
    执行关系分析和数据存储，完成工作流。
    """
    print("--- Executing Finalization Stage ---")

    # 1. 确保我们有经过审核的事件数据
    events_to_process = state.reviewed_events
    if events_to_process is None: # 如果用户直接确认，reviewed_events可能为空，此时使用extracted_events
        events_to_process = state.extracted_events

    if not events_to_process:
        print("No events to process. Finalizing workflow as completed.")
        return state_manager.update_state(state, new_stage="completed")

    # 2. 初始化并运行 RelationshipAnalysisAgent
    try:
        print("Analyzing event relationships...")
        relationship_agent = RelationshipAnalysisAgent(llm_config=LLM_CONFIG_DEEPSEEK)
        
        # 构建 agent 需要的输入消息
        analysis_prompt = f"""
        Based on the following extracted events, please analyze and identify any relationships between them (e.g., causal, temporal, related).

        Extracted Events:
        {json.dumps(events_to_process, indent=2, ensure_ascii=False)}
        """
        
        response = await asyncio.to_thread(
            relationship_agent.generate_reply,
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        relationships = json.loads(response)
        print(f"Found {len(relationships)} relationship(s).")

    except Exception as e:
        print(f"Error during relationship analysis: {e}")
        return state_manager.update_state(state, new_stage="failed", error_message=f"Relationship analysis failed: {e}")

    # 3. 初始化并运行 StorageAgent (模拟存储)
    try:
        print("Saving events and relationships...")
        storage_agent = StorageAgent() # StorageAgent 通常没有LLM配置
        
        # 模拟调用存储工具
        storage_agent.save_events_and_relationships(
            events=events_to_process,
            relationships=relationships
        )
        print("Data saved successfully.")

    except Exception as e:
        print(f"Error during data storage: {e}")
        return state_manager.update_state(state, new_stage="failed", error_message=f"Storage failed: {e}")

    # 4. 清理审核文件
    if REVIEW_REQUEST_FILE.exists():
        REVIEW_REQUEST_FILE.unlink()

    # 5. 更新最终状态并保存
    print("Workflow completed successfully.")
    return state_manager.update_state(
        state,
        new_stage="completed",
        final_relationships=relationships
    )
