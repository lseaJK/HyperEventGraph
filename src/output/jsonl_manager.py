"""JSONL输出管理器

实现事件和关系数据的标准化JSONL格式输出功能，支持增量写入和格式验证。
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import asdict

# 尝试相对导入，如果失败则使用绝对导入
try:
    from ..event_logic.data_models import EventRelation
    from ..event_logic.local_models import Event
except ImportError:
    import sys
    from pathlib import Path
    # 添加项目根目录到路径
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.event_logic.data_models import EventRelation
    from src.event_logic.local_models import Event


class JSONLManager:
    """JSONL输出管理器"""
    
    def __init__(self, output_dir: str = "output"):
        """初始化JSONL管理器
        
        Args:
            output_dir: 输出目录路径
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def write_events_to_jsonl(self, 
                             events: List[Event], 
                             filename: str = None,
                             append: bool = False) -> str:
        """将事件列表写入JSONL文件
        
        Args:
            events: 事件列表
            filename: 输出文件名，如果为None则自动生成
            append: 是否追加模式写入
            
        Returns:
            str: 输出文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"events_{timestamp}.jsonl"
            
        filepath = self.output_dir / filename
        mode = 'a' if append else 'w'
        
        with open(filepath, mode, encoding='utf-8') as f:
            for event in events:
                event_dict = self._event_to_dict(event)
                f.write(json.dumps(event_dict, ensure_ascii=False) + '\n')
                
        return str(filepath)
    
    def write_relations_to_jsonl(self, 
                                relations: List[EventRelation], 
                                filename: str = None,
                                append: bool = False) -> str:
        """将关系列表写入JSONL文件
        
        Args:
            relations: 关系列表
            filename: 输出文件名，如果为None则自动生成
            append: 是否追加模式写入
            
        Returns:
            str: 输出文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"relations_{timestamp}.jsonl"
            
        filepath = self.output_dir / filename
        mode = 'a' if append else 'w'
        
        with open(filepath, mode, encoding='utf-8') as f:
            for relation in relations:
                relation_dict = relation.to_dict()
                f.write(json.dumps(relation_dict, ensure_ascii=False) + '\n')
                
        return str(filepath)
    
    def write_combined_to_jsonl(self, 
                               events: List[Event], 
                               relations: List[EventRelation],
                               filename: str = None,
                               append: bool = False) -> str:
        """将事件和关系合并写入JSONL文件
        
        Args:
            events: 事件列表
            relations: 关系列表
            filename: 输出文件名，如果为None则自动生成
            append: 是否追加模式写入
            
        Returns:
            str: 输出文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"combined_{timestamp}.jsonl"
            
        filepath = self.output_dir / filename
        mode = 'a' if append else 'w'
        
        with open(filepath, mode, encoding='utf-8') as f:
            # 写入事件数据
            for event in events:
                event_dict = self._event_to_dict(event)
                event_dict['data_type'] = 'event'
                f.write(json.dumps(event_dict, ensure_ascii=False) + '\n')
            
            # 写入关系数据
            for relation in relations:
                relation_dict = relation.to_dict()
                relation_dict['data_type'] = 'relation'
                f.write(json.dumps(relation_dict, ensure_ascii=False) + '\n')
                
        return str(filepath)
    
    def append_event_to_jsonl(self, event: Event, filename: str) -> None:
        """向JSONL文件追加单个事件
        
        Args:
            event: 事件对象
            filename: 目标文件名
        """
        filepath = self.output_dir / filename
        
        with open(filepath, 'a', encoding='utf-8') as f:
            event_dict = self._event_to_dict(event)
            f.write(json.dumps(event_dict, ensure_ascii=False) + '\n')
    
    def append_relation_to_jsonl(self, relation: EventRelation, filename: str) -> None:
        """向JSONL文件追加单个关系
        
        Args:
            relation: 关系对象
            filename: 目标文件名
        """
        filepath = self.output_dir / filename
        
        with open(filepath, 'a', encoding='utf-8') as f:
            relation_dict = relation.to_dict()
            f.write(json.dumps(relation_dict, ensure_ascii=False) + '\n')
    
    def read_events_from_jsonl(self, filename: str) -> List[Dict[str, Any]]:
        """从JSONL文件读取事件数据
        
        Args:
            filename: 文件名
            
        Returns:
            List[Dict[str, Any]]: 事件字典列表
        """
        filepath = self.output_dir / filename
        events = []
        
        if not filepath.exists():
            return events
            
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event_dict = json.loads(line)
                        if event_dict.get('data_type') == 'event' or 'data_type' not in event_dict:
                            events.append(event_dict)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing line: {line}, Error: {e}")
                        
        return events
    
    def read_relations_from_jsonl(self, filename: str) -> List[Dict[str, Any]]:
        """从JSONL文件读取关系数据
        
        Args:
            filename: 文件名
            
        Returns:
            List[Dict[str, Any]]: 关系字典列表
        """
        filepath = self.output_dir / filename
        relations = []
        
        if not filepath.exists():
            return relations
            
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        relation_dict = json.loads(line)
                        if relation_dict.get('data_type') == 'relation' or 'data_type' not in relation_dict:
                            relations.append(relation_dict)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing line: {line}, Error: {e}")
                        
        return relations
    
    def validate_jsonl_format(self, filename: str) -> Dict[str, Any]:
        """验证JSONL文件格式
        
        Args:
            filename: 文件名
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        filepath = self.output_dir / filename
        result = {
            'is_valid': True,
            'total_lines': 0,
            'valid_lines': 0,
            'invalid_lines': 0,
            'errors': []
        }
        
        if not filepath.exists():
            result['is_valid'] = False
            result['errors'].append(f"File {filename} does not exist")
            return result
            
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                result['total_lines'] += 1
                line = line.strip()
                
                if not line:
                    continue
                    
                try:
                    json.loads(line)
                    result['valid_lines'] += 1
                except json.JSONDecodeError as e:
                    result['invalid_lines'] += 1
                    result['errors'].append(f"Line {line_num}: {str(e)}")
                    result['is_valid'] = False
                    
        return result
    
    def get_file_stats(self, filename: str) -> Dict[str, Any]:
        """获取JSONL文件统计信息
        
        Args:
            filename: 文件名
            
        Returns:
            Dict[str, Any]: 文件统计信息
        """
        filepath = self.output_dir / filename
        stats = {
            'exists': False,
            'size_bytes': 0,
            'line_count': 0,
            'event_count': 0,
            'relation_count': 0,
            'created_time': None,
            'modified_time': None
        }
        
        if not filepath.exists():
            return stats
            
        stats['exists'] = True
        file_stat = filepath.stat()
        stats['size_bytes'] = file_stat.st_size
        stats['created_time'] = datetime.fromtimestamp(file_stat.st_ctime).isoformat()
        stats['modified_time'] = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    stats['line_count'] += 1
                    try:
                        data = json.loads(line)
                        data_type = data.get('data_type', 'unknown')
                        if data_type == 'event' or ('event_id' in data and 'relation_type' not in data):
                            stats['event_count'] += 1
                        elif data_type == 'relation' or 'relation_type' in data:
                            stats['relation_count'] += 1
                    except json.JSONDecodeError:
                        pass
                        
        return stats
    
    def _event_to_dict(self, event: Event) -> Dict[str, Any]:
        """将Event对象转换为字典格式
        
        Args:
            event: Event对象
            
        Returns:
            Dict[str, Any]: 事件字典
        """
        if hasattr(event, 'to_dict'):
            return event.to_dict()
        else:
            # 如果Event对象没有to_dict方法，使用dataclass的asdict
            event_dict = asdict(event) if hasattr(event, '__dataclass_fields__') else event.__dict__.copy()
            
            # 处理datetime对象
            for key, value in event_dict.items():
                if isinstance(value, datetime):
                    event_dict[key] = value.isoformat()
                    
            return event_dict
    
    def list_output_files(self) -> List[str]:
        """列出输出目录中的所有JSONL文件
        
        Returns:
            List[str]: JSONL文件名列表
        """
        if not self.output_dir.exists():
            return []
            
        return [f.name for f in self.output_dir.glob('*.jsonl')]
    
    def cleanup_old_files(self, days: int = 30) -> List[str]:
        """清理指定天数之前的旧文件
        
        Args:
            days: 保留天数
            
        Returns:
            List[str]: 被删除的文件名列表
        """
        if not self.output_dir.exists():
            return []
            
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        deleted_files = []
        
        for file_path in self.output_dir.glob('*.jsonl'):
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                deleted_files.append(file_path.name)
                
        return deleted_files