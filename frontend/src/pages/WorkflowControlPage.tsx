import React, { useEffect, useRef } from 'react';
import { Typography, Paper, Box, Alert, Button, Stack, Grid } from '@mui/material';
import { useSystemStore } from '../store/systemStore';
import { useLogStore } from '../store/logStore';
import { startWorkflow, stopWorkflow } from '../services/api.ts';
import { connectWebSocket, disconnectWebSocket } from '../services/websocket';
import { WorkflowDetail } from '../components/workflows/WorkflowDetail';
import { FullPipelineControl } from '../components/workflows/FullPipelineControl';

const WorkflowList: React.FC = () => {
  const { workflows, error, fetchWorkflows } = useSystemStore();
  const { addLog } = useLogStore();

  useEffect(() => {
    fetchWorkflows();
    // 定期刷新工作流状态
    const interval = setInterval(() => {
      fetchWorkflows();
    }, 10000); // 10秒刷新一次
    
    return () => clearInterval(interval);
  }, [fetchWorkflows]);

  const handleStartWorkflow = async (workflowName: string, params: Record<string, any>) => {
    try {
      // 将前端参数转换为API期望的格式
      const apiParams: Record<string, any> = {};
      
      // 根据参数类型进行转换
      Object.entries(params).forEach(([key, value]) => {
        if (typeof value === 'string' && !isNaN(Number(value))) {
          if (value.includes('.')) {
            apiParams[key] = parseFloat(value);
          } else {
            apiParams[key] = parseInt(value);
          }
        } else {
          apiParams[key] = value;
        }
      });
      
      // 添加日志消息
      addLog(`正在启动工作流: ${workflowName}`);
      if (Object.keys(apiParams).length > 0) {
        addLog(`使用参数: ${JSON.stringify(apiParams)}`);
      }
      
      // 调用API启动工作流
      await startWorkflow(workflowName, apiParams);
      
      // 启动成功后立即重新获取工作流状态
      fetchWorkflows();
    } catch (error) {
      console.error(`Failed to start workflow ${workflowName}:`, error);
      addLog(`启动工作流失败: ${workflowName}, 错误: ${error}`);
    }
  };

  const handleStopWorkflow = async (workflowName: string) => {
    try {
      addLog(`正在停止工作流: ${workflowName}...`);
      await stopWorkflow(workflowName);
      addLog(`工作流 ${workflowName} 已停止 ⏹️`);
      
      // 停止成功后立即重新获取工作流状态
      fetchWorkflows();
    } catch (error) {
      console.error(`Failed to stop workflow ${workflowName}:`, error);
      addLog(`停止工作流失败: ${workflowName}, 错误: ${error}`);
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 2, height: '100%', overflowY: 'auto' }}>
      <Typography variant="h6" gutterBottom>
        工作流控制中心
      </Typography>
      
      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {workflows.map((workflow) => (
        <WorkflowDetail 
          key={workflow.name}
          workflow={workflow}
          onStart={handleStartWorkflow}
          onStop={handleStopWorkflow}
        />
      ))}
    </Paper>
  );
};

const LogViewer: React.FC = () => {
  const { logs, clearLogs } = useLogStore();
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to the bottom
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <Paper elevation={3} sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6">
          实时日志
        </Typography>
        <Button variant="outlined" size="small" onClick={clearLogs}>
          清除日志
        </Button>
      </Box>
      <Paper
        variant="outlined"
        ref={logContainerRef}
        sx={{
          flexGrow: 1,
          overflowY: 'auto',
          p: 2,
          backgroundColor: '#f5f5f5',
          fontFamily: 'monospace',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}
      >
        {logs.map((log, index) => (
          <div key={index}>{`> ${log}`}</div>
        ))}
      </Paper>
    </Paper>
  );
};


export const WorkflowControlPage: React.FC = () => {
  const { addLog } = useLogStore();
  const { fetchWorkflows } = useSystemStore();

  const handleRefresh = () => {
    fetchWorkflows();
  };

  useEffect(() => {
    // Establish WebSocket connection on mount
    connectWebSocket(addLog);

    // Disconnect on unmount
    return () => {
      disconnectWebSocket();
    };
  }, [addLog]);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        HyperEventGraph 工作流控制中心
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 3 }}>
        构建事件知识图谱的完整流程控制和监控平台
      </Typography>
      
      <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} sx={{ height: 'calc(100vh - 160px)' }}>
        {/* 全流程控制面板 */}
        <Box sx={{ flex: '0 0 350px', height: '100%' }}>
          <FullPipelineControl onRefresh={handleRefresh} />
        </Box>
        
        {/* 工作流列表 */}
        <Box sx={{ flex: '0 0 400px', height: '100%', overflowY: 'auto' }}>
          <WorkflowList />
        </Box>
        
        {/* 日志查看器 */}
        <Box sx={{ flex: 1, height: '100%' }}>
          <LogViewer />
        </Box>
      </Stack>
    </Box>
  );
};
