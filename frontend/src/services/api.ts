import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8080/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- API 类型定义 ---

export interface SystemStatus {
  [key: string]: number;
}

export interface WorkflowStatus {
  name: string;
  status: 'Idle' | 'Running' | 'Failed' | 'Completed';
  last_run: string | null;
}

export interface EventData {
  id: string;
  event_type: string;
  trigger: string;
  involved_entities: { entity_name: string; entity_type: string }[];
  event_summary: string;
  source_text?: string;
}

export interface EventRowData extends EventData {}

// Graph Data Types
export interface GraphNode {
  id: string;
  name: string;
  type: 'Event' | 'Entity';
}

export interface GraphLink {
  source: string;
  target: string;
  label: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}


// --- API 请求函数 ---

export const getStatus = async (): Promise<SystemStatus> => {
  try {
    const response = await apiClient.get('/status');
    return response.data;
  } catch (error) {
    console.error('获取状态失败:', error);
    // 返回备用数据，避免UI崩溃
    return {
      pending_triage: 10,
      pending_extraction: 30,
      completed: 60
    };
  }
};

export const getWorkflows = async (): Promise<WorkflowStatus[]> => {
  try {
    const response = await apiClient.get('/workflows');
    return response.data;
  } catch (error) {
    console.error('获取工作流失败:', error);
    // 返回备用数据
    return [
      { name: 'triage', status: 'Idle', last_run: null },
      { name: 'extraction', status: 'Idle', last_run: null },
      { name: 'learning', status: 'Idle', last_run: null },
      { name: 'cortex', status: 'Idle', last_run: null },
      { name: 'relationship_analysis', status: 'Idle', last_run: null }
    ];
  }
};

export const startWorkflow = async (workflowName: string): Promise<any> => {
  try {
    const response = await apiClient.post(`/workflow/${workflowName}/start`);
    return response.data;
  } catch (error) {
    console.error(`启动工作流 ${workflowName} 失败:`, error);
    throw error;
  }
};

export const getEvents = async (page: number, pageSize: number): Promise<{ rows: EventRowData[], rowCount: number }> => {
  try {
    const response = await apiClient.get(`/events?page=${page}&page_size=${pageSize}`);
    return response.data;
  } catch (error) {
    console.error('获取事件数据失败:', error);
    
    // 返回备用模拟数据
    const mockData: EventData[] = Array.from({ length: 100 }, (_, i) => ({
      id: `evt_${i + 1}`,
      event_type: i % 5 === 0 ? '合作签约' : '产品发布',
      trigger: i % 5 === 0 ? '签署协议' : '推出',
      involved_entities: [
        { entity_name: `公司A-${i}`, entity_type: 'ORG' },
        { entity_name: `产品B-${i}`, entity_type: 'PRODUCT' },
      ],
      event_summary: `公司A-${i} 与合作伙伴签署了关于 产品B-${i} 的合作协议。`,
      source_text: `...原始文本片段 ${i}...`,
    }));

    const rows = mockData.slice(page * pageSize, (page + 1) * pageSize);
    return { rows, rowCount: mockData.length };
  }
};

export const getGraphData = async (): Promise<GraphData> => {
  try {
    const response = await apiClient.get('/graph');
    return response.data;
  } catch (error) {
    console.error('获取图谱数据失败:', error);
    
    // 返回备用图谱数据
    const nodes: GraphNode[] = [
      { id: 'Event1', name: '合作签约', type: 'Event' },
      { id: 'Event2', name: '产品发布', type: 'Event' },
      { id: 'Org1', name: '公司A', type: 'Entity' },
      { id: 'Product1', name: '产品B', type: 'Entity' },
      { id: 'Org2', name: '公司C', type: 'Entity' },
    ];

    const links: GraphLink[] = [
      { source: 'Org1', target: 'Event1', label: 'INVOLVED_IN' },
      { source: 'Product1', target: 'Event1', label: 'INVOLVED_IN' },
      { source: 'Org2', target: 'Event2', label: 'INVOLVED_IN' },
      { source: 'Event1', target: 'Event2', label: 'PRECEDES' },
    ];

    return { nodes, links };
  }
};

export default apiClient;
