import { create } from 'zustand';
import { getStatus, getWorkflows } from '../services/api.ts';
import type { SystemStatus, WorkflowStatus } from '../services/api.ts';

interface SystemState {
  statusSummary: SystemStatus;
  workflows: WorkflowStatus[];
  loading: boolean;
  error: string | null;
  fetchStatus: () => Promise<void>;
  fetchWorkflows: () => Promise<void>;
}

export const useSystemStore = create<SystemState>((set) => ({
  // 初始状态
  statusSummary: {},
  workflows: [],
  loading: false,
  error: null,

  // 异步 action，用于从API获取数据并更新状态
  fetchStatus: async () => {
    try {
      set({ loading: true, error: null });
      const summary = await getStatus();
      set({ statusSummary: summary, loading: false });
    } catch (error) {
      console.error('Failed to fetch status:', error);
      set({ 
        error: 'Failed to connect to backend. Using mock data.',
        loading: false,
        // 使用模拟数据作为后备
        statusSummary: {
          'pending_triage': 25882,
          'pending_extraction': 64754,
          'completed': 7372,
        }
      });
    }
  },

  fetchWorkflows: async () => {
    try {
      set({ loading: true, error: null });
      const workflows = await getWorkflows();
      set({ workflows, loading: false });
    } catch (error) {
      console.error('Failed to fetch workflows:', error);
      // 使用备用数据
      const fallbackWorkflows = [
        { name: 'triage', status: 'Idle', last_run: null },
        { name: 'extraction', status: 'Idle', last_run: null },
        { name: 'learning', status: 'Idle', last_run: null },
        { name: 'cortex', status: 'Idle', last_run: null },
        { name: 'relationship_analysis', status: 'Idle', last_run: null },
      ] as WorkflowStatus[];
      
      set({ 
        workflows: fallbackWorkflows,
        error: 'Using fallback data. Backend may not be running.',
        loading: false 
      });
    }
  },
}));
