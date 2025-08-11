import React, { useEffect, useRef } from 'react';
import { Typography, Grid, Paper, Box, List, ListItem, ListItemText, Button, Divider } from '@mui/material';
import { useSystemStore } from '../store/systemStore';
import { useLogStore } from '../store/logStore';
import { startWorkflow } from '../services/api.ts';
import { connectWebSocket, disconnectWebSocket } from '../services/websocket';

const WorkflowList: React.FC = () => {
  const { workflows, fetchWorkflows } = useSystemStore();

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  const handleStart = async (workflowName: string) => {
    try {
      await startWorkflow(workflowName);
      // Optionally, add a notification for the user
    } catch (error) {
      console.error(`Failed to start workflow ${workflowName}:`, error);
      // Optionally, add an error notification
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 2, height: '100%' }}>
      <Typography variant="h6" gutterBottom>
        Workflow Control
      </Typography>
      <List>
        {workflows.map((wf) => (
          <ListItem key={wf.name} divider>
            <ListItemText primary={wf.name} secondary={`Status: ${wf.status}`} />
            <Button
              variant="contained"
              size="small"
              onClick={() => handleStart(wf.name)}
              disabled={wf.status === 'Running'}
            >
              Start
            </Button>
          </ListItem>
        ))}
      </List>
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
          Real-time Logs
        </Typography>
        <Button variant="outlined" size="small" onClick={clearLogs}>
          Clear Logs
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
        Workflow Control Center
      </Typography>
      <Grid container spacing={3} sx={{ height: 'calc(100vh - 120px)' }}>
        <Grid item xs={12} md={5}>
          <WorkflowList />
        </Grid>
        <Grid item xs={12} md={7}>
          <LogViewer />
        </Grid>
      </Grid>
    </Box>
  );
};
