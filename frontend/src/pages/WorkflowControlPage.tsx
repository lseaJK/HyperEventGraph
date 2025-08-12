import React, { useEffect, useRef } from 'react';
import { Typography, Paper, Box, Alert, Button, Stack } from '@mui/material';
import { useSystemStore } from '../store/systemStore';
import { useLogStore } from '../store/logStore';
import { startWorkflow } from '../services/api.ts';
import { connectWebSocket, disconnectWebSocket } from '../services/websocket';
import { WorkflowDetail } from '../components/workflows/WorkflowDetail';

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
      // 在控制台输出参数，以便调试
      console.log(`Starting workflow ${workflowName} with params:`, params);
      
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
        工作流控制中心
      </Typography>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ height: 'calc(100vh - 120px)' }}>
        <Box sx={{ flex: '0 0 40%', height: '100%', overflowY: 'auto' }}>
          <WorkflowList />
        </Box>
        <Box sx={{ flex: '0 0 60%', height: '100%' }}>
          <LogViewer />
        </Box>
      </Stack>
    </Box>
  );
};
