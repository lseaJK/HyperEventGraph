import { create } from 'zustand';
import { SystemStatus, WorkflowStatus } from '../services/api';

interface SystemState {
  statusSummary: SystemStatus;
  workflows: WorkflowStatus[];
  fetchStatus: () => Promise<void>;
  fetchWorkflows: () => Promise<void>;
}

export const useSystemStore = create<SystemState>((set) => ({
  // 初始状态
  statusSummary: {},
  workflows: [],

  // 异步 action，用于从API获取数据并更新状态
  fetchStatus: async () => {
    // 在这里可以引入 api.ts 中的函数
    // const summary = await getStatus();
    // set({ statusSummary: summary });
    // 示例数据：
    set({
      statusSummary: {
        'pending_triage': 25882,
        'pending_extraction': 64754,
        'completed': 7372,
      }
    });
  },

  fetchWorkflows: async () => {
    // const workflows = await getWorkflows();
    // set({ workflows });
    // 示例数据：
    set({
      workflows: [
        { name: 'Triage', status: 'Idle', last_run: '2025-08-11 10:00:00' },
        { name: 'Extraction', status: 'Running', last_run: '2025-08-11 11:30:00' },
        { name: 'Cortex', status: 'Failed', last_run: '2025-08-10 15:45:00' },
        { name: 'Relations', status: 'Completed', last_run: '2025-08-09 20:00:00' },
      ]
    })
  },
}));
