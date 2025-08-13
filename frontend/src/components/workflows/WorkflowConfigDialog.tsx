import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Box,
  Chip,
  Divider,
} from '@mui/material';
import { Settings } from '@mui/icons-material';

export interface WorkflowConfig {
  batch_size?: number;
  extraction_mode?: string;
  learning_mode?: string;
  confidence_threshold?: number;
  clustering_threshold?: number;
  analysis_depth?: string;
  min_cluster_size?: number;
  dbscan_eps?: number;
}

interface ConfigDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (config: WorkflowConfig) => void;
  workflowName: string;
  initialConfig?: WorkflowConfig;
}

// 工作流特定的默认配置
const DEFAULT_CONFIGS: Record<string, WorkflowConfig> = {
  triage: {
    batch_size: 100,
    confidence_threshold: 0.8,
  },
  extraction: {
    batch_size: 50,
    extraction_mode: 'standard',
    confidence_threshold: 0.7,
  },
  learning: {
    learning_mode: 'incremental',
    batch_size: 30,
    confidence_threshold: 0.75,
  },
  cortex: {
    clustering_threshold: 0.6,
    min_cluster_size: 3,
    dbscan_eps: 0.5,
    analysis_depth: 'medium',
  },
  relationship_analysis: {
    analysis_depth: 'deep',
    confidence_threshold: 0.8,
    min_cluster_size: 2,
  },
};

// 参数描述和验证规则
const PARAM_INFO = {
  batch_size: {
    label: '批处理大小',
    description: '每批处理的数据条数',
    type: 'number',
    min: 1,
    max: 1000,
  },
  extraction_mode: {
    label: '抽取模式',
    description: '事件抽取的模式选择',
    type: 'select',
    options: ['standard', 'enhanced', 'fast'],
  },
  learning_mode: {
    label: '学习模式',
    description: '机器学习的训练模式',
    type: 'select',
    options: ['incremental', 'batch', 'online'],
  },
  confidence_threshold: {
    label: '置信度阈值',
    description: '结果筛选的最低置信度',
    type: 'number',
    min: 0,
    max: 1,
    step: 0.05,
  },
  clustering_threshold: {
    label: '聚类阈值',
    description: '聚类算法的相似度阈值',
    type: 'number',
    min: 0,
    max: 1,
    step: 0.05,
  },
  analysis_depth: {
    label: '分析深度',
    description: '分析过程的详细程度',
    type: 'select',
    options: ['shallow', 'medium', 'deep'],
  },
  min_cluster_size: {
    label: '最小聚类大小',
    description: '形成有效聚类的最少元素数',
    type: 'number',
    min: 1,
    max: 50,
  },
  dbscan_eps: {
    label: 'DBSCAN 距离参数',
    description: 'DBSCAN聚类算法的邻域距离',
    type: 'number',
    min: 0.1,
    max: 2,
    step: 0.1,
  },
};

export const WorkflowConfigDialog: React.FC<ConfigDialogProps> = ({
  open,
  onClose,
  onConfirm,
  workflowName,
  initialConfig = {},
}) => {
  const [config, setConfig] = useState<WorkflowConfig>(() => ({
    ...DEFAULT_CONFIGS[workflowName],
    ...initialConfig,
  }));

  const handleReset = () => {
    setConfig(DEFAULT_CONFIGS[workflowName] || {});
  };

  const handleConfirm = () => {
    // 过滤掉未设置的参数
    const cleanConfig = Object.fromEntries(
      Object.entries(config).filter(([_, value]) => value !== undefined && value !== null && value !== '')
    );
    onConfirm(cleanConfig);
  };

  const renderConfigField = (key: string, info: any) => {
    if (info.type === 'select') {
      return (
        <FormControl fullWidth margin="normal">
          <InputLabel>{info.label}</InputLabel>
          <Select
            value={config[key as keyof WorkflowConfig] || ''}
            onChange={(e) => setConfig(prev => ({ ...prev, [key]: e.target.value }))}
          >
            {info.options.map((option: string) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      );
    } else {
      return (
        <TextField
          fullWidth
          margin="normal"
          label={info.label}
          type={info.type}
          value={config[key as keyof WorkflowConfig] || ''}
          onChange={(e) => setConfig(prev => ({ 
            ...prev, 
            [key]: info.type === 'number' ? Number(e.target.value) : e.target.value 
          }))}
          inputProps={{
            min: info.min,
            max: info.max,
            step: info.step,
          }}
          helperText={info.description}
        />
      );
    }
  };

  // 获取工作流相关的参数
  const getRelevantParams = () => {
    const workflowDefaults = DEFAULT_CONFIGS[workflowName];
    if (!workflowDefaults) return Object.keys(PARAM_INFO);
    
    return Object.keys(workflowDefaults);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <Settings />
          <Typography variant="h6">
            配置工作流: {workflowName}
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box mb={2}>
          <Typography variant="body2" color="text.secondary">
            调整以下参数来优化工作流执行。未设置的参数将使用系统默认值。
          </Typography>
        </Box>

        <Box mb={2}>
          <Typography variant="subtitle2" gutterBottom>
            当前配置预览:
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            {Object.entries(config)
              .filter(([_, value]) => value !== undefined && value !== null && value !== '')
              .map(([key, value]) => (
                <Chip
                  key={key}
                  label={`${PARAM_INFO[key as keyof typeof PARAM_INFO]?.label || key}: ${value}`}
                  variant="outlined"
                  size="small"
                />
              ))}
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box display="flex" flexWrap="wrap" gap={2}>
          {getRelevantParams().map((paramKey) => (
            <Box key={paramKey} flex="1 1 300px" minWidth="300px">
              {renderConfigField(paramKey, PARAM_INFO[paramKey as keyof typeof PARAM_INFO])}
            </Box>
          ))}
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={handleReset} color="secondary">
          重置为默认值
        </Button>
        <Button onClick={onClose}>
          取消
        </Button>
        <Button onClick={handleConfirm} variant="contained">
          应用配置
        </Button>
      </DialogActions>
    </Dialog>
  );
};
