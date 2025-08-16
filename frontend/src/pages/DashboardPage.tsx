import React, { useEffect } from 'react';
import { Typography, Grid, Paper, Box, List, ListItem, ListItemText, Chip } from '@mui/material';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useSystemStore } from '../store/systemStore';
import type { WorkflowStatus } from '../services/api.ts';

// --- Helper Functions & Data ---

const COLORS = {
  pending_triage: '#FFBB28',
  pending_review: '#FF8042', 
  pending_extraction: '#8884d8',
  pending_clustering: '#82ca9d',
  pending_relationship_analysis: '#ffc658',
  completed: '#00C49F',
};

const statusColorMap: { [key: string]: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning" } = {
  Idle: 'default',
  Running: 'primary',
  Failed: 'error',
  Completed: 'success',
};

const WorkflowStatusList: React.FC<{ workflows: WorkflowStatus[] }> = ({ workflows }) => (
  <Paper elevation={3} sx={{ p: 2, height: '100%' }}>
    <Typography variant="h6" gutterBottom>
      Workflow Status
    </Typography>
    <List>
      {workflows.map((wf) => (
        <ListItem key={wf.name} divider>
          <ListItemText primary={wf.name} secondary={`Last run: ${wf.last_run || 'Never'}`} />
          <Chip label={wf.status} color={statusColorMap[wf.status]} size="small" />
        </ListItem>
      ))}
    </List>
  </Paper>
);

const StatusPieChart: React.FC<{ data: { name: string; value: number }[] }> = ({ data }) => (
  <Paper elevation={3} sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
    <Typography variant="h6" gutterBottom>
      Global Data Status
    </Typography>
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          outerRadius={80}
          fill="#8884d8"
          dataKey="value"
          nameKey="name"
          label={({ name, percent }) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[entry.name as keyof typeof COLORS] || '#8884d8'} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  </Paper>
);


// --- Main Component ---

export const DashboardPage: React.FC = () => {
  const { statusSummary, workflows, fetchStatus, fetchWorkflows } = useSystemStore();

  useEffect(() => {
    // Fetch data when the component mounts
    fetchStatus();
    fetchWorkflows();
  }, [fetchStatus, fetchWorkflows]);

  const pieChartData = Object.entries(statusSummary).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8 }}>
          <StatusPieChart data={pieChartData} />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <WorkflowStatusList workflows={workflows} />
        </Grid>
      </Grid>
    </Box>
  );
};
