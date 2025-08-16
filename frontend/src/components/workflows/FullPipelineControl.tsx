import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Button,
  Box,
  Stack,
  Alert,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  TextField,
  Chip,
  LinearProgress
} from '@mui/material';
import {
  PlayArrow,
  Refresh,
  Storage,
  AccountTree,
  AutoAwesome
} from '@mui/icons-material';
import { importData, runFullPipeline, resetSystem } from '../../services/api';
import { useLogStore } from '../../store/logStore';

interface FullPipelineControlProps {
  onRefresh?: () => void;
}

export const FullPipelineControl: React.FC<FullPipelineControlProps> = ({ onRefresh }) => {
  const { addLog } = useLogStore();
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState('');
  const [progress, setProgress] = useState(0);
  const [dataFile, setDataFile] = useState('IC_data/filtered_data.json');
  const [includeImport, setIncludeImport] = useState(true);
  const [concurrency, setConcurrency] = useState(3);

  const steps = [
    { name: '数据导入', key: 'import' },
    { name: '事件分类', key: 'triage' },
    { name: '事件提取', key: 'extraction' },
    { name: '事件聚类', key: 'cortex' },
    { name: '关系分析', key: 'relationship' },
    { name: '知识图谱', key: 'graph' }
  ];

  const handleImportData = async () => {
    try {
      setIsRunning(true);
      setCurrentStep('正在导入数据...');
      setProgress(20);
      
      addLog(`🔄 开始导入数据: ${dataFile}`);
      
      const result = await importData(dataFile);
      
      addLog(`✅ 数据导入成功: ${JSON.stringify(result)}`);
      setProgress(100);
      
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      addLog(`❌ 数据导入失败: ${error}`);
    } finally {
      setIsRunning(false);
      setCurrentStep('');
      setProgress(0);
    }
  };

  const handleRunFullPipeline = async () => {
    try {
      setIsRunning(true);
      setProgress(0);
      
      addLog('🚀 开始执行完整的事件知识图谱构建流程');
      addLog(`📊 配置参数: 导入数据=${includeImport}, 并发数=${concurrency}, 数据文件=${dataFile}`);
      
      // 模拟进度更新
      const progressSteps = [
        { step: '初始化系统', progress: 10 },
        { step: '数据导入', progress: 20 },
        { step: '事件分类 (Triage)', progress: 35 },
        { step: '事件提取 (Extraction)', progress: 50 },
        { step: '事件聚类 (Cortex)', progress: 70 },
        { step: '关系分析 (Relationship)', progress: 85 },
        { step: '构建知识图谱', progress: 95 }
      ];

      for (const { step, progress: stepProgress } of progressSteps) {
        setCurrentStep(step);
        setProgress(stepProgress);
        addLog(`🔄 ${step}...`);
        await new Promise(resolve => setTimeout(resolve, 1000)); // 模拟处理时间
      }
      
      const result = await runFullPipeline({
        importData: includeImport,
        dataFile: includeImport ? dataFile : undefined,
        concurrency
      });
      
      setProgress(100);
      setCurrentStep('完成');
      addLog('🎉 完整流程执行成功！');
      addLog(`📈 结果摘要: ${JSON.stringify(result)}`);
      
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      addLog(`❌ 流程执行失败: ${error}`);
    } finally {
      setIsRunning(false);
      setCurrentStep('');
      setProgress(0);
    }
  };

  const handleResetSystem = async () => {
    try {
      setIsRunning(true);
      setCurrentStep('重置系统...');
      setProgress(50);
      
      addLog('🔄 正在重置系统状态...');
      
      const result = await resetSystem();
      
      addLog('✅ 系统重置成功');
      addLog(`📊 重置结果: ${JSON.stringify(result)}`);
      setProgress(100);
      
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      addLog(`❌ 系统重置失败: ${error}`);
    } finally {
      setIsRunning(false);
      setCurrentStep('');
      setProgress(0);
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 3, height: '100%' }}>
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <AutoAwesome color="primary" />
        全流程控制中心
      </Typography>
      
      <Alert severity="info" sx={{ mb: 2 }}>
        一键执行从数据导入到知识图谱生成的完整流程
      </Alert>

      {/* 配置选项 */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>配置选项</Typography>
        
        <Stack spacing={2}>
          <FormControl size="small" fullWidth>
            <InputLabel>数据文件</InputLabel>
            <Select
              value={dataFile}
              onChange={(e) => setDataFile(e.target.value)}
              label="数据文件"
              disabled={isRunning}
            >
              <MenuItem value="IC_data/filtered_data.json">科创板完整数据</MenuItem>
              <MenuItem value="IC_data/filtered_data_demo.json">演示数据</MenuItem>
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Switch
                checked={includeImport}
                onChange={(e) => setIncludeImport(e.target.checked)}
                disabled={isRunning}
              />
            }
            label="包含数据导入"
          />

          <TextField
            label="并发处理数"
            type="number"
            size="small"
            value={concurrency}
            onChange={(e) => setConcurrency(parseInt(e.target.value) || 3)}
            disabled={isRunning}
            inputProps={{ min: 1, max: 10 }}
          />
        </Stack>
      </Box>

      <Divider sx={{ my: 2 }} />

      {/* 进度显示 */}
      {isRunning && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            当前步骤: {currentStep}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{ height: 8, borderRadius: 4 }}
          />
          <Typography variant="caption" color="text.secondary">
            {progress}% 完成
          </Typography>
        </Box>
      )}

      {/* 流程步骤指示器 */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>流程步骤</Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {steps.map((step, index) => (
            <Chip
              key={step.key}
              label={step.name}
              size="small"
              color={progress > (index + 1) * 16 ? 'success' : 'default'}
              variant={progress > (index + 1) * 16 ? 'filled' : 'outlined'}
            />
          ))}
        </Stack>
      </Box>

      <Divider sx={{ my: 2 }} />

      {/* 控制按钮 */}
      <Stack spacing={2}>
        <Button
          variant="contained"
          size="large"
          fullWidth
          startIcon={<PlayArrow />}
          onClick={handleRunFullPipeline}
          disabled={isRunning}
          sx={{ py: 1.5 }}
        >
          {isRunning ? '执行中...' : '执行完整流程'}
        </Button>

        <Stack direction="row" spacing={2}>
          <Button
            variant="outlined"
            startIcon={<Storage />}
            onClick={handleImportData}
            disabled={isRunning}
            fullWidth
          >
            仅导入数据
          </Button>

          <Button
            variant="outlined"
            color="warning"
            startIcon={<Refresh />}
            onClick={handleResetSystem}
            disabled={isRunning}
            fullWidth
          >
            重置系统
          </Button>
        </Stack>
      </Stack>

      {/* 状态说明 */}
      <Box sx={{ mt: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
        <Typography variant="caption" color="text.secondary">
          💡 提示: 完整流程包括数据导入 → 事件分类 → 事件提取 → 事件聚类 → 关系分析 → 知识图谱构建
        </Typography>
      </Box>
    </Paper>
  );
};
