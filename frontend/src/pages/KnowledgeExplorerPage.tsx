import React, { useState, useEffect } from 'react';
import { Typography, Box, Paper, List, ListItem, ListItemText, Chip } from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef } from '@mui/x-data-grid';
// import ForceGraph2D from 'react-force-graph-2d';
import { getEvents, getGraphData } from '../services/api.ts';
import type { EventRowData, GraphData } from '../services/api.ts';

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

  useEffect(() => {
    getGraphData()
      .then(data => {
        console.log('Raw graph data:', data);
        // Convert 'edges' to 'links' if needed (API sometimes returns 'edges')
        const processedData = {
          nodes: data.nodes || [],
          links: data.links || (data as any).edges || []
        };
        console.log('Processed graph data:', processedData);
        setGraphData(processedData);
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

  return (
    <Paper sx={{ height: '100%', width: '100%', position: 'relative' }}>
       <Typography variant="h6" sx={{ p: 2, position: 'absolute', top: 0, left: 0, zIndex: 1 }}>
        Knowledge Graph ({graphData.nodes.length} nodes, {graphData.links.length} links)
      </Typography>
      {graphData.nodes.length > 0 ? (
        <Box sx={{ p: 2, pt: 8 }}>
          <Typography variant="subtitle1" gutterBottom>
            Nodes ({graphData.nodes.length}):
          </Typography>
          <Box sx={{ mb: 2 }}>
            {graphData.nodes.map((node) => (
              <Box key={node.id} sx={{ mb: 1, p: 1, border: '1px solid #ddd', borderRadius: 1 }}>
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
            <Box key={index} sx={{ mb: 1, p: 1, border: '1px solid #eee', borderRadius: 1 }}>
              <Typography variant="body2">
                {link.source} → {link.target} ({link.label})
              </Typography>
            </Box>
          ))}
        </Box>
      ) : (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <Typography>No graph data available</Typography>
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
