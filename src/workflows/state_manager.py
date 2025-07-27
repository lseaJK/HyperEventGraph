# src/workflows/state_manager.py

import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from pathlib import Path

# 定义工作流的各个阶段
VALID_STAGES = [
    "pending_triage",
    "awaiting_triage_review",
    "pending_extraction",
    "awaiting_extraction_review",
    "pending_finalization",
    "completed",
    "failed"
]

class TriageResult(BaseModel):
    """分流结果的数据模型"""
    status: str
    domain: str
    event_type: str
    confidence: Optional[float] = 0.0

class WorkflowState(BaseModel):
    """
    定义工作流状态文件的完整结构
    """
    workflow_id: str
    input_file: Optional[str] = None
    current_stage: str = "pending_triage"
    
    original_text: Optional[str] = None
    triage_result: Optional[TriageResult] = None
    
    extracted_events: List[Dict[str, Any]] = Field(default_factory=list)
    reviewed_events: Optional[List[Dict[str, Any]]] = None
    
    final_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    
    error_message: Optional[str] = None
    history: List[str] = Field(default_factory=list)

class StateManager:
    """
    
负责管理工作流状态的读取、写入和更新
    """
    def __init__(self, state_file_path: str = "workflow_state.json"):
        self.state_file = Path(state_file_path)

    def initialize_state(self, workflow_id: str, input_file: str) -> WorkflowState:
        """创建一个新的工作流状态"""
        initial_state = WorkflowState(
            workflow_id=workflow_id,
            input_file=input_file,
            history=[f"Workflow '{workflow_id}' initialized for file '{input_file}'."]
        )
        self.save_state(initial_state)
        return initial_state

    def load_state(self) -> Optional[WorkflowState]:
        """从文件加载工作流状态"""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return WorkflowState(**data)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error loading state file: {e}")
            return None

    def save_state(self, state: WorkflowState):
        """将当前工作流状态保存到文件"""
        state.history.append(f"State saved at stage: {state.current_stage}")
        with open(self.state_file, 'w', encoding='utf-8') as f:
            # Pydantic's model_dump_json is preferred for correct serialization
            f.write(state.model_dump_json(indent=4))

    def update_state(self, state: WorkflowState, new_stage: str, **kwargs) -> WorkflowState:
        """
        更新状态对象的属性并保存
        
        Args:
            state (WorkflowState): 当前的状态对象
            new_stage (str): 要转换到的新阶段
            **kwargs: 要更新的其他属性
        """
        if new_stage not in VALID_STAGES:
            raise ValueError(f"Invalid stage: {new_stage}. Must be one of {VALID_STAGES}")
            
        state.current_stage = new_stage
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
            else:
                raise AttributeError(f"WorkflowState has no attribute '{key}'")
        
        self.save_state(state)
        return state

if __name__ == '__main__':
    # --- 示例用法 ---
    state_manager = StateManager("test_workflow_state.json")

    # 1. 初始化状态
    print("1. Initializing new workflow state...")
    state = state_manager.initialize_state(workflow_id="test001", input_file="data/sample.json")
    print(f"   - Initial stage: {state.current_stage}")

    # 2. 加载状态
    print("\n2. Loading state from file...")
    loaded_state = state_manager.load_state()
    if loaded_state:
        print(f"   - Loaded stage: {loaded_state.current_stage}")
        print(f"   - Workflow ID: {loaded_state.workflow_id}")

    # 3. 更新状态
    print("\n3. Updating state to 'awaiting_triage_review'...")
    triage_res = TriageResult(status="known", domain="financial", event_type="company_merger_and_acquisition")
    updated_state = state_manager.update_state(
        loaded_state,
        new_stage="awaiting_triage_review",
        triage_result=triage_res
    )
    print(f"   - New stage: {updated_state.current_stage}")
    print(f"   - Triage result added: {updated_state.triage_result}")

    # 清理测试文件
    import os
    os.remove("test_workflow_state.json")
    print("\nCleaned up test state file.")

