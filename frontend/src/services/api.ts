import axios from 'axios';

// 动态构建API base URL，适配服务器端口映射
const getApiBaseURL = () => {
  const protocol = window.location.protocol;
  const host = window.location.hostname;
  
  // 如果是开发环境且访问localhost，使用8080端口
  // 否则使用当前页面的端口（适配服务器端口映射）
  let port = window.location.port;
  if (host === 'localhost' || host === '127.0.0.1') {
    port = '8080';
  }
  
  const baseUrl = `${protocol}//${host}:${port}/api`;
  console.log('API Base URL:', baseUrl);
  return baseUrl;
};

const apiClient = axios.create({
  baseURL: getApiBaseURL(),
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

export const startWorkflow = async (workflowName: string, params?: Record<string, any>): Promise<any> => {
  try {
    const response = await apiClient.post(`/workflow/${workflowName}/start`, params);
    return response.data;
  } catch (error) {
    console.error(`启动工作流 ${workflowName} 失败:`, error);
    throw error;
  }
};

export const stopWorkflow = async (workflowName: string): Promise<any> => {
  try {
    const response = await apiClient.post(`/workflow/${workflowName}/stop`);
    return response.data;
  } catch (error) {
    console.error(`停止工作流 ${workflowName} 失败:`, error);
    throw error;
  }
};

export const getWorkflowStatus = async (workflowName: string): Promise<any> => {
  try {
    const response = await apiClient.get(`/workflow/${workflowName}/status`);
    return response.data;
  } catch (error) {
    console.error(`获取工作流状态 ${workflowName} 失败:`, error);
    throw error;
  }
};

export const getEvents = async (page: number, pageSize: number): Promise<{ rows: EventRowData[], rowCount: number }> => {
  try {
    const response = await apiClient.get(`/events?page=${page}&page_size=${pageSize}`);
    const data = response.data;
    
    // 适配API返回的实际格式
    const apiRows = data.events || [];
    const apiRowCount = data.pagination?.total || 0;
    
    // 如果API返回空数据，使用模拟数据进行测试
    if (apiRows.length === 0 && apiRowCount === 0) {
      console.log('API返回空数据，使用模拟数据进行测试');
      const mockData: EventData[] = Array.from({ length: 50 }, (_, i) => ({
        id: `evt_${i + 1}`,
        event_type: i % 3 === 0 ? '合作签约' : (i % 3 === 1 ? '产品发布' : '技术突破'),
        trigger: i % 3 === 0 ? '签署协议' : (i % 3 === 1 ? '推出产品' : '研发成功'),
        involved_entities: [
          { entity_name: `公司${String.fromCharCode(65 + i % 26)}`, entity_type: 'Organization' },
          { entity_name: `产品${i + 1}`, entity_type: 'Product' },
        ],
        event_summary: `公司${String.fromCharCode(65 + i % 26)} 在 产品${i + 1} 方面取得了重要进展。`,
        source_text: `这是第${i + 1}个事件的原始文本片段...`,
      }));

      const rows = mockData.slice(page * pageSize, (page + 1) * pageSize);
      return { rows, rowCount: mockData.length };
    }
    
    return {
      rows: apiRows,
      rowCount: apiRowCount
    };
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
    const data = response.data;
    
    // 适配API返回的实际格式（edges -> links）
    return {
      nodes: data.nodes || [],
      links: data.links || data.edges || []
    };
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
