import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- API 类型定义 ---

// 对应后端的全局状态统计
export interface SystemStatus {
  [key: string]: number;
}

// 对应后端的单个工作流状态
export interface WorkflowStatus {
  name: string;
  status: 'Idle' | 'Running' | 'Failed' | 'Completed';
  last_run: string | null;
  // 可以根据后端返回添加更多字段，如 progress
}

// --- API 请求函数 ---

/**
 * 获取系统宏观状态统计
 */
export const getStatus = async (): Promise<SystemStatus> => {
  const response = await apiClient.get('/status');
  return response.data;
};

/**
 * 获取所有工作流的状态
 */
export const getWorkflows = async (): Promise<WorkflowStatus[]> => {
  // 假设后端有 /workflows 端点
  const response = await apiClient.get('/workflows');
  return response.data;
};

/**
 * 启动一个工作流
 * @param workflowName 工作流名称
 */
export const startWorkflow = async (workflowName: string): Promise<any> => {
  const response = await apiClient.post(`/workflow/${workflowName}/start`);
  return response.data;
};

// 后续可以继续添加 getEvents, getGraph 等函数...

export default apiClient;
