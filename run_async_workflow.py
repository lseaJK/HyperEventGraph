# run_async_workflow.py

import argparse
import json
import uuid
import asyncio
from pathlib import Path

from src.workflows.state_manager import StateManager, WorkflowState
from src.workflows.stages import (
    execute_triage_stage, 
    execute_extraction_stage, 
    execute_finalization_stage
)

# --- 用户交互处理 ---
def process_user_response(state: WorkflowState, response_path: Path, state_manager: StateManager) -> WorkflowState:
    """
    处理用户在 review_response.txt 中提供的反馈。
    """
    print("--- Processing User Response ---")
    try:
        response_text = response_path.read_text(encoding='utf-8').strip()
        
        next_stage = None
        update_data = {}

        # 方案1: 简单的状态确认/拒绝
        if response_text.lower() == "status: confirmed":
            print("User confirmed. Proceeding to the next stage.")
            if state.current_stage == "awaiting_triage_review":
                next_stage = "pending_extraction"
            elif state.current_stage == "awaiting_extraction_review":
                next_stage = "pending_finalization"
        
        elif response_text.lower() == "status: rejected":
            print("User rejected. Halting workflow.")
            next_stage = "failed"
            update_data['error_message'] = "Workflow halted by user rejection."

        # 方案2: 用户提供了修正后的JSON数据
        else:
            try:
                corrected_data = json.loads(response_text)
                print("User provided corrected data.")
                if state.current_stage == "awaiting_triage_review":
                    # 假设用户修正了分流结果
                    update_data['triage_result'] = corrected_data
                    next_stage = "pending_extraction"
                elif state.current_stage == "awaiting_extraction_review":
                    # 假设用户修正了抽取结果
                    update_data['reviewed_events'] = corrected_data
                    next_stage = "pending_finalization"
            except json.JSONDecodeError:
                print(f"Invalid response format in '{response_path.name}'. It's not a valid command or JSON.")
                # 保持当前状态，不进行任何操作
                return state

        # 更新状态
        if next_stage:
            state = state_manager.update_state(state, new_stage=next_stage, **update_data)
            print(f"Workflow state updated to '{next_stage}'.")

    except Exception as e:
        print(f"Error processing user response: {e}")
        # 出错时保持当前状态
    
    finally:
        # 清理回复文件，避免重复处理
        response_path.unlink()
        print(f"Cleaned up '{response_path.name}'.")

    return state

# --- 主控制器 ---
class WorkflowController:
    def __init__(self, state_file: str = "workflow_state.json"):
        self.state_manager = StateManager(state_file)
        self.response_file = Path("review_response.txt")
        
        # 阶段与执行函数的映射
        self.stage_executors = {
            "pending_triage": execute_triage_stage,
            "pending_extraction": execute_extraction_stage,
            "pending_finalization": execute_finalization_stage,
        }

    async def run(self, input_file: str = None):
        """主执行循环"""
        
        # 1. 加载或初始化状态
        state = self.state_manager.load_state()
        
        if input_file:
            if state and state.current_stage not in ["completed", "failed"]:
                print(f"An active workflow is already in progress (stage: {state.current_stage}).")
                print("Please complete or reset it before starting a new one.")
                return
            print(f"Starting a new workflow for input file: {input_file}")
            workflow_id = str(uuid.uuid4())
            state = self.state_manager.initialize_state(workflow_id, input_file)
        
        if not state:
            print("No active workflow found. Please start a new one with --input <file_path>")
            return

        print(f"\n--- Current Workflow State ---")
        print(f"ID: {state.workflow_id}")
        print(f"File: {state.input_file}")
        print(f"Stage: {state.current_stage}")
        print("----------------------------")

        # 2. 处理用户响应
        if self.response_file.exists():
            state = process_user_response(state, self.response_file, self.state_manager)
        
        # 3. 根据当前阶段执行相应的操作
        executor = self.stage_executors.get(state.current_stage)
        
        if executor:
            # 将 state_manager 传递给执行函数
            state = await executor(state, self.state_manager)
        elif state.current_stage in ["awaiting_triage_review", "awaiting_extraction_review"]:
            print(f"Workflow is paused, awaiting user review in 'review_request.txt'.")
            print(f"Please provide your feedback in '{self.response_file.name}' and run the script again.")
        elif state.current_stage == "completed":
            print("Workflow has been successfully completed.")
        elif state.current_stage == "failed":
            print(f"Workflow failed with error: {state.error_message}")
        else:
            print(f"Unknown stage: {state.current_stage}. Halting.")

def main():
    parser = argparse.ArgumentParser(description="Asynchronous Event Extraction Workflow")
    parser.add_argument("--input", type=str, help="Path to the input JSON file to start a new workflow.")
    
    args = parser.parse_args()
    
    controller = WorkflowController()
    asyncio.run(controller.run(input_file=args.input))

if __name__ == "__main__":
    main()