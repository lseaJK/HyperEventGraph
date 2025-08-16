import React, { useState, useEffect } from 'react';
import { Typography, Box, Paper, ToggleButtonGroup, ToggleButton } from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef } from '@mui/x-data-grid';
import ForceGraph2D from 'react-force-graph-2d';
import { getEvents, getGraphData } from '../services/api.ts';
import type { EventRowData, GraphData } from '../services/api.ts';
import { ViewList, AccountTree } from '@mui/icons-material';

// --- Event Data Table Component ---

const tableColumns: GridColDef[] = [
  { field: 'id', headerName: 'Event ID', width: 120 },
  { field: 'event_type', headerName: 'Event Type', width: 150 },
  { field: 'trigger', headerName: 'Trigger', width: 150 },
  {
    field: 'involved_entities',
    headerName: 'Involved Entities',
    width: 300,
    valueGetter: (value: { entity_name: string; entity_type: string }[]) => {
      if (!value || !Array.isArray(value)) return '';
      return value.map(e => `${e.entity_name} (${e.entity_type})`).join(', ');
    },
  },
  {
    field: 'event_summary',
    headerName: 'Summary',
    flex: 1,
  },
];

const EventDataTable: React.FC = () => {
  const [rows, setRows] = useState<EventRowData[]>([]);
  const [rowCount, setRowCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 10 });

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const { rows: newRows, rowCount: newRowCount } = await getEvents(
          paginationModel.page,
          paginationModel.pageSize
        );
        if (active) {
          setRows(newRows);
          setRowCount(newRowCount || newRows.length);
          setLoading(false);
        }
      } catch (error) {
        console.error('Failed to load events:', error);
        if (active) {
          setRows([]);
          setRowCount(0);
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, [paginationModel]);

  return (
    <Paper sx={{ height: '100%', width: '100%' }}>
      <DataGrid
        rows={rows}
        columns={tableColumns}
        rowCount={rowCount}
        loading={loading}
        pageSizeOptions={[10, 25, 50]}
        paginationModel={paginationModel}
        paginationMode="server"
        onPaginationModelChange={setPaginationModel}
      />
    </Paper>
  );
};

// --- Knowledge Graph Component ---

const KnowledgeGraph: React.FC = () => {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'force' | 'list'>('force');

  useEffect(() => {
    getGraphData()
      .then(data => {
        console.log('Raw graph data:', data);
        setGraphData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load graph data:', err);
        setError('Failed to load graph data');
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <Paper sx={{ height: '100%', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography>Loading graph...</Typography>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper sx={{ height: '100%', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography color="error">{error}</Typography>
      </Paper>
    );
  }

  const nodeColor = (node: any) => {
    return node.type === 'Event' ? '#ff6b6b' : '#4ecdc4';
  };

  const linkColor = (link: any) => {
    switch (link.label) {
      case 'INVOLVED_IN': return '#ffd93d';
      case 'PRECEDES': return '#6bcf7f';
      case 'COOPERATES_WITH': return '#4d79ff';
      case 'RELATED_TO': return '#ff9ff3';
      default: return '#999';
    }
  };

  return (
    <Paper sx={{ height: '100%', width: '100%', position: 'relative' }}>
      <Box sx={{ p: 2, borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          Knowledge Graph ({graphData.nodes.length} nodes, {graphData.links.length} links)
        </Typography>
        <Box>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, newMode) => newMode && setViewMode(newMode)}
            size="small"
          >
            <ToggleButton value="force">
              <AccountTree />
            </ToggleButton>
            <ToggleButton value="list">
              <ViewList />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>
      
      {viewMode === 'force' && graphData.nodes.length > 0 ? (
        <Box sx={{ height: 'calc(100% - 80px)' }}>
          <ForceGraph2D
            graphData={graphData}
            nodeLabel="name"
            nodeVal={8}
            nodeColor={nodeColor}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const label = node.name || '';
              const fontSize = 12/globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              const textWidth = ctx.measureText(label).width;
              const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

              // 绘制节点背景圆圈
              ctx.fillStyle = nodeColor(node);
              ctx.beginPath();
              ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI, false);
              ctx.fill();

              // 绘制文字背景
              ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
              ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);

              // 绘制文字
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = 'black';
              ctx.fillText(label, node.x, node.y);
            }}
            linkLabel="label"
            linkColor={linkColor}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}
            linkWidth={2}
            width={800}
            height={500}
            backgroundColor="#f8f9fa"
            onNodeClick={(node) => {
              console.log('Node clicked:', node);
            }}
            onLinkClick={(link) => {
              console.log('Link clicked:', link);
            }}
            cooldownTicks={100}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
          />
        </Box>
      ) : (
        <Box sx={{ p: 2, height: 'calc(100% - 80px)', overflow: 'auto' }}>
          <Typography variant="subtitle1" gutterBottom>
            Nodes ({graphData.nodes.length}):
          </Typography>
          <Box sx={{ mb: 2 }}>
            {graphData.nodes.map((node) => (
              <Box key={node.id} sx={{ 
                mb: 1, 
                p: 1, 
                border: '1px solid #ddd', 
                borderRadius: 1,
                backgroundColor: node.type === 'Event' ? '#fff5f5' : '#f0ffff'
              }}>
                <Typography variant="body2">
                  <strong>{node.name || node.id}</strong> ({node.type})
                </Typography>
              </Box>
            ))}
          </Box>
          <Typography variant="subtitle1" gutterBottom>
            Links ({graphData.links.length}):
          </Typography>
          {graphData.links.map((link, index) => (
            <Box key={index} sx={{ 
              mb: 1, 
              p: 1, 
              border: '1px solid #eee', 
              borderRadius: 1,
              backgroundColor: '#fafafa'
            }}>
              <Typography variant="body2">
                <span style={{ fontWeight: 'bold', color: '#2196f3' }}>{link.source}</span> 
                {' → '}
                <span style={{ fontWeight: 'bold', color: '#ff9800' }}>{link.target}</span>
                {link.label && (
                  <span style={{ 
                    marginLeft: 8, 
                    padding: '2px 8px', 
                    backgroundColor: '#e3f2fd', 
                    borderRadius: 4, 
                    fontSize: '0.75rem' 
                  }}>
                    {link.label}
                  </span>
                )}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Paper>
  );
};


// --- Main Page Component ---

export const KnowledgeExplorerPage: React.FC = () => {
  return (
    <Box sx={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h4" gutterBottom sx={{ flexShrink: 0, p: 2 }}>
        Knowledge Explorer
      </Typography>
      <Box sx={{ flexGrow: 1, p: 2, display: 'flex', gap: 2 }}>
        <Box sx={{ flex: '1 1 60%', minHeight: 0 }}>
          <EventDataTable />
        </Box>
        <Box sx={{ flex: '1 1 40%', minHeight: 0 }}>
          <KnowledgeGraph />
        </Box>
      </Box>
    </Box>
  );
};
