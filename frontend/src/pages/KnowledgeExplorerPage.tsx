import React, { useState, useEffect } from 'react';
import { Typography, Box, Paper } from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef } from '@mui/x-data-grid';
import ForceGraph2D from 'react-force-graph-2d';
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
    valueGetter: (value: { entity_name: string; entity_type: string }[]) =>
      value.map(e => `${e.entity_name} (${e.entity_type})`).join(', '),
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
      const { rows: newRows, rowCount: newRowCount } = await getEvents(
        paginationModel.page,
        paginationModel.pageSize
      );
      if (active) {
        setRows(newRows);
        setRowCount(newRowCount);
        setLoading(false);
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

  useEffect(() => {
    getGraphData().then(setGraphData);
  }, []);

  return (
    <Paper sx={{ height: '100%', width: '100%', position: 'relative' }}>
       <Typography variant="h6" sx={{ p: 2, position: 'absolute', top: 0, left: 0 }}>
        Knowledge Graph
      </Typography>
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="name"
        nodeAutoColorBy="type"
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        linkLabel="label"
      />
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
