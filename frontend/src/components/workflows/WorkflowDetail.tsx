import React, { useState } from 'react';
import { 
  Card, 
  CardHeader, 
  CardContent, 
  CardActions, 
  Button, 
  Typography, 
  Collapse, 
  Box, 
  Chip, 
  TextField, 
  FormControl, 
  InputLabel, 
  Select, 
  MenuItem, 
  LinearProgress,
  Divider
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import SettingsIcon from '@mui/icons-material/Settings';
import type { WorkflowStatus } from '../../services/api';
import { WorkflowConfigDialog, type WorkflowConfig as ConfigDialogConfig } from './WorkflowConfigDialog';

// 工作流配置接口
interface WorkflowConfig {
  [key: string]: {
    title: string;
    description: string;
    config: {
      [key: string]: {
        type: 'text' | 'number' | 'select';
        label: string;
        default: string | number;
        options?: string[];
      };
    };
  };
}

// 预定义工作流配置
const workflowConfigs: WorkflowConfig = {
  extraction: {
    title: "事件抽取工作流",
    description: "从文本中抽取结构化事件信息，将非结构化数据转换为知识图谱节点",
    config: {
      batch_size: {
        type: 'number',
        label: '批处理大小',
        default: 10
      },
      extraction_mode: {
        type: 'select',
        label: '抽取模式',
        default: 'standard',
        options: ['standard', 'detailed', 'minimal']
      }
    }
  },
  learning: {
    title: "知识学习工作流",
    description: "从未知事件中学习新的事件类型，扩展系统的知识边界",
    config: {
      clustering_threshold: {
        type: 'number',
        label: '聚类阈值',
        default: 0.75
      },
      learning_mode: {
        type: 'select',
        label: '学习模式',
        default: 'interactive',
        options: ['interactive', 'autonomous', 'semi-supervised']
      }
    }
  },
  triage: {
    title: "事件分类工作流",
    description: "对输入文本进行初步事件分类，识别已知和未知事件类型",
    config: {
      confidence_threshold: {
        type: 'number',
        label: '置信度阈值',
        default: 0.7
      }
    }
  },
  cortex: {
    title: "Cortex智能分析",
    description: "深度分析事件集合，识别事件模式并生成高级故事单元",
    config: {
      dbscan_eps: {
        type: 'number',
        label: '聚类距离阈值',
        default: 0.5
      },
      min_cluster_size: {
        type: 'number',
        label: '最小簇大小',
        default: 3
      }
    }
  },
  relationship_analysis: {
    title: "关系分析工作流",
    description: "分析事件和实体之间的多维关系，构建完整知识图谱",
    config: {
      analysis_depth: {
        type: 'select',
        label: '分析深度',
        default: 'standard',
        options: ['minimal', 'standard', 'deep']
      }
    }
  }
};

interface WorkflowDetailProps {
  workflow: WorkflowStatus;
  onStart: (name: string, params: Record<string, any>) => void;
  onStop?: (name: string) => void;
}

export const WorkflowDetail: React.FC<WorkflowDetailProps> = ({ 
  workflow, 
  onStart,
  onStop
}) => {
  const [expanded, setExpanded] = useState(false);
  const [params, setParams] = useState<Record<string, any>>({});
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  
  const config = workflowConfigs[workflow.name] || {
    title: workflow.name.charAt(0).toUpperCase() + workflow.name.slice(1),
    description: `${workflow.name} 工作流`,
    config: {}
  };
  
  // 初始化默认参数
  React.useEffect(() => {
    const defaultParams: Record<string, any> = {};
    Object.entries(config.config).forEach(([key, field]) => {
      defaultParams[key] = field.default;
    });
    setParams(defaultParams);
  }, [workflow.name]);
  
  const handleParamChange = (key: string, value: any) => {
    setParams(prev => ({ ...prev, [key]: value }));
  };
  
  const handleToggleExpand = () => {
    setExpanded(!expanded);
  };
  
  const handleStart = () => {
    onStart(workflow.name, params);
  };
  
  const handleStop = () => {
    if (onStop) {
      onStop(workflow.name);
    }
  };

  const handleConfigApply = (config: ConfigDialogConfig) => {
    setParams(config);
    setConfigDialogOpen(false);
  };
  
  // 状态颜色映射
  const statusColors: Record<string, "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning"> = {
    Idle: 'default',
    Running: 'primary',
    Failed: 'error',
    Completed: 'success',
  };
  
  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardHeader
        title={
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">{config.title}</Typography>
            <Chip 
              label={workflow.status} 
              color={statusColors[workflow.status] || 'default'} 
              size="small"
            />
          </Box>
        }
        subheader={config.description}
        action={
          <Button
            onClick={handleToggleExpand}
            aria-expanded={expanded}
            aria-label="show more"
            endIcon={expanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          >
            {expanded ? '收起' : '配置'}
          </Button>
        }
      />
      
      {workflow.status === 'Running' && (
        <LinearProgress variant="indeterminate" sx={{ height: 4 }} />
      )}
      
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            工作流配置参数
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, my: 2 }}>
            {Object.entries(config.config).map(([key, field]) => (
              <FormControl key={key} variant="outlined" size="small" fullWidth>
                {field.type === 'select' ? (
                  <>
                    <InputLabel id={`${workflow.name}-${key}-label`}>{field.label}</InputLabel>
                    <Select
                      labelId={`${workflow.name}-${key}-label`}
                      value={params[key] || field.default}
                      onChange={(e) => handleParamChange(key, e.target.value)}
                      label={field.label}
                    >
                      {field.options?.map(option => (
                        <MenuItem key={option} value={option}>{option}</MenuItem>
                      ))}
                    </Select>
                  </>
                ) : (
                  <TextField
                    label={field.label}
                    type={field.type}
                    value={params[key] || field.default}
                    onChange={(e) => handleParamChange(key, e.target.value)}
                    size="small"
                  />
                )}
              </FormControl>
            ))}
          </Box>
          
          {workflow.last_run && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="body2" color="text.secondary">
                上次运行: {workflow.last_run}
              </Typography>
            </>
          )}
        </CardContent>
      </Collapse>
      
      <CardActions sx={{ justifyContent: 'flex-end' }}>
        {workflow.status === 'Running' ? (
          <Button 
            variant="outlined" 
            color="error" 
            startIcon={<StopIcon />}
            onClick={handleStop}
          >
            停止
          </Button>
        ) : (
          <Box sx={{ display: 'flex', gap: 1 }}>
            {/* 配置按钮 */}
            <Button 
              variant="outlined" 
              color="secondary" 
              startIcon={<SettingsIcon />}
              onClick={() => setConfigDialogOpen(true)}
            >
              高级配置
            </Button>
            
            {/* 为抽取和学习模式添加特殊按钮 */}
            {workflow.name === 'extraction' && (
              <Button 
                variant="outlined" 
                color="info" 
                startIcon={<PlayArrowIcon />}
                onClick={() => {
                  handleParamChange('extraction_mode', 'detailed');
                  handleStart();
                }}
              >
                详细模式
              </Button>
            )}
            {workflow.name === 'learning' && (
              <Button 
                variant="outlined" 
                color="info" 
                startIcon={<PlayArrowIcon />}
                onClick={() => {
                  handleParamChange('learning_mode', 'interactive');
                  handleStart();
                }}
              >
                交互模式
              </Button>
            )}
            <Button 
              variant="contained" 
              color="primary" 
              startIcon={<PlayArrowIcon />}
              onClick={handleStart}
            >
              启动
            </Button>
          </Box>
        )}
      </CardActions>

      {/* 配置对话框 */}
      <WorkflowConfigDialog
        open={configDialogOpen}
        onClose={() => setConfigDialogOpen(false)}
        onConfirm={handleConfigApply}
        workflowName={workflow.name}
        initialConfig={params}
      />
    </Card>
  );
};
