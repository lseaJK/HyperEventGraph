"""格式验证器

验证导出文件的格式正确性和数据完整性。
"""

import json
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    format_type: str
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'is_valid': self.is_valid,
            'format_type': self.format_type,
            'errors': self.errors,
            'warnings': self.warnings,
            'metadata': self.metadata
        }


class FormatValidator:
    """格式验证器"""
    
    def __init__(self):
        """初始化验证器"""
        self.supported_formats = {
            '.jsonl': self._validate_jsonl,
            '.json': self._validate_json,
            '.graphml': self._validate_graphml,
            '.gexf': self._validate_gexf,
            '.csv': self._validate_csv
        }
    
    def validate_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """验证文件格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                format_type='unknown',
                errors=[f"File does not exist: {file_path}"],
                warnings=[],
                metadata={}
            )
        
        file_ext = file_path.suffix.lower()
        
        if file_ext not in self.supported_formats:
            return ValidationResult(
                is_valid=False,
                format_type='unsupported',
                errors=[f"Unsupported file format: {file_ext}"],
                warnings=[],
                metadata={'file_size': file_path.stat().st_size}
            )
        
        try:
            return self.supported_formats[file_ext](file_path)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                format_type=file_ext[1:],  # 去掉点号
                errors=[f"Validation error: {str(e)}"],
                warnings=[],
                metadata={'file_size': file_path.stat().st_size}
            )
    
    def _validate_jsonl(self, file_path: Path) -> ValidationResult:
        """验证JSONL格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []
        metadata = {
            'file_size': file_path.stat().st_size,
            'line_count': 0,
            'valid_json_lines': 0,
            'event_count': 0,
            'relation_count': 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    metadata['line_count'] = line_num
                    
                    line = line.strip()
                    if not line:
                        warnings.append(f"Empty line at line {line_num}")
                        continue
                    
                    try:
                        data = json.loads(line)
                        metadata['valid_json_lines'] += 1
                        
                        # 检查数据类型
                        if isinstance(data, dict):
                            if 'event_id' in data or 'title' in data:
                                metadata['event_count'] += 1
                            elif 'source_event_id' in data and 'target_event_id' in data:
                                metadata['relation_count'] += 1
                            
                            # 验证必要字段
                            self._validate_json_structure(data, line_num, errors, warnings)
                        else:
                            warnings.append(f"Line {line_num}: Expected object, got {type(data).__name__}")
                    
                    except json.JSONDecodeError as e:
                        errors.append(f"Line {line_num}: Invalid JSON - {str(e)}")
        
        except Exception as e:
            errors.append(f"File reading error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format_type='jsonl',
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    def _validate_json(self, file_path: Path) -> ValidationResult:
        """验证JSON格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []
        metadata = {
            'file_size': file_path.stat().st_size
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证图数据结构
            if isinstance(data, dict):
                if 'nodes' in data and 'edges' in data:
                    # 图格式
                    nodes = data.get('nodes', [])
                    edges = data.get('edges', [])
                    
                    metadata.update({
                        'node_count': len(nodes),
                        'edge_count': len(edges),
                        'has_metadata': 'metadata' in data
                    })
                    
                    # 验证节点
                    for i, node in enumerate(nodes):
                        if not isinstance(node, dict):
                            errors.append(f"Node {i}: Expected object, got {type(node).__name__}")
                        elif 'id' not in node:
                            errors.append(f"Node {i}: Missing required field 'id'")
                    
                    # 验证边
                    for i, edge in enumerate(edges):
                        if not isinstance(edge, dict):
                            errors.append(f"Edge {i}: Expected object, got {type(edge).__name__}")
                        else:
                            required_fields = ['source', 'target']
                            for field in required_fields:
                                if field not in edge:
                                    errors.append(f"Edge {i}: Missing required field '{field}'")
                else:
                    # 单个对象
                    self._validate_json_structure(data, 1, errors, warnings)
            elif isinstance(data, list):
                # 对象数组
                metadata['item_count'] = len(data)
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        self._validate_json_structure(item, i + 1, errors, warnings)
                    else:
                        warnings.append(f"Item {i + 1}: Expected object, got {type(item).__name__}")
            else:
                errors.append(f"Root element: Expected object or array, got {type(data).__name__}")
        
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {str(e)}")
        except Exception as e:
            errors.append(f"File reading error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format_type='json',
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    def _validate_graphml(self, file_path: Path) -> ValidationResult:
        """验证GraphML格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []
        metadata = {
            'file_size': file_path.stat().st_size,
            'node_count': 0,
            'edge_count': 0,
            'key_count': 0
        }
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 检查根元素
            if root.tag != '{http://graphml.graphdrawing.org/xmlns}graphml' and root.tag != 'graphml':
                errors.append(f"Invalid root element: expected 'graphml', got '{root.tag}'")
            
            # 检查命名空间
            if 'xmlns' not in root.attrib:
                warnings.append("Missing xmlns namespace declaration")
            
            # 统计元素
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                
                if tag == 'key':
                    metadata['key_count'] += 1
                    # 验证key元素
                    if 'id' not in elem.attrib:
                        errors.append(f"Key element missing 'id' attribute")
                    if 'for' not in elem.attrib:
                        errors.append(f"Key element missing 'for' attribute")
                
                elif tag == 'node':
                    metadata['node_count'] += 1
                    if 'id' not in elem.attrib:
                        errors.append(f"Node element missing 'id' attribute")
                
                elif tag == 'edge':
                    metadata['edge_count'] += 1
                    required_attrs = ['source', 'target']
                    for attr in required_attrs:
                        if attr not in elem.attrib:
                            errors.append(f"Edge element missing '{attr}' attribute")
            
            # 检查图结构
            graphs = root.findall('.//{http://graphml.graphdrawing.org/xmlns}graph') or root.findall('.//graph')
            if not graphs:
                errors.append("No graph element found")
            elif len(graphs) > 1:
                warnings.append(f"Multiple graph elements found ({len(graphs)})")
        
        except ET.ParseError as e:
            errors.append(f"XML parsing error: {str(e)}")
        except Exception as e:
            errors.append(f"File reading error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format_type='graphml',
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    def _validate_gexf(self, file_path: Path) -> ValidationResult:
        """验证GEXF格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []
        metadata = {
            'file_size': file_path.stat().st_size,
            'node_count': 0,
            'edge_count': 0,
            'attribute_count': 0
        }
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 检查根元素
            if root.tag != '{http://www.gexf.net/1.2draft}gexf' and root.tag != 'gexf':
                errors.append(f"Invalid root element: expected 'gexf', got '{root.tag}'")
            
            # 检查版本
            if 'version' not in root.attrib:
                warnings.append("Missing version attribute")
            
            # 统计元素
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                
                if tag == 'attribute':
                    metadata['attribute_count'] += 1
                    # 验证attribute元素
                    required_attrs = ['id', 'title', 'type']
                    for attr in required_attrs:
                        if attr not in elem.attrib:
                            errors.append(f"Attribute element missing '{attr}' attribute")
                
                elif tag == 'node':
                    metadata['node_count'] += 1
                    if 'id' not in elem.attrib:
                        errors.append(f"Node element missing 'id' attribute")
                
                elif tag == 'edge':
                    metadata['edge_count'] += 1
                    required_attrs = ['source', 'target']
                    for attr in required_attrs:
                        if attr not in elem.attrib:
                            errors.append(f"Edge element missing '{attr}' attribute")
            
            # 检查必要的子元素
            graphs = root.findall('.//{http://www.gexf.net/1.2draft}graph') or root.findall('.//graph')
            if not graphs:
                errors.append("No graph element found")
        
        except ET.ParseError as e:
            errors.append(f"XML parsing error: {str(e)}")
        except Exception as e:
            errors.append(f"File reading error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format_type='gexf',
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    def _validate_csv(self, file_path: Path) -> ValidationResult:
        """验证CSV格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []
        metadata = {
            'file_size': file_path.stat().st_size,
            'row_count': 0,
            'column_count': 0,
            'has_header': False
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 检测分隔符
                sample = f.read(1024)
                f.seek(0)
                
                sniffer = csv.Sniffer()
                try:
                    dialect = sniffer.sniff(sample)
                    delimiter = dialect.delimiter
                except:
                    delimiter = ','
                    warnings.append("Could not detect CSV dialect, using comma as delimiter")
                
                reader = csv.reader(f, delimiter=delimiter)
                
                first_row = True
                expected_columns = None
                
                for row_num, row in enumerate(reader, 1):
                    metadata['row_count'] = row_num
                    
                    if first_row:
                        metadata['column_count'] = len(row)
                        expected_columns = len(row)
                        
                        # 检查是否有标题行
                        if all(isinstance(cell, str) and not cell.isdigit() for cell in row if cell.strip()):
                            metadata['has_header'] = True
                        
                        first_row = False
                    else:
                        # 检查列数一致性
                        if len(row) != expected_columns:
                            errors.append(f"Row {row_num}: Expected {expected_columns} columns, got {len(row)}")
                    
                    # 检查空行
                    if all(not cell.strip() for cell in row):
                        warnings.append(f"Row {row_num}: Empty row")
                
                if metadata['row_count'] == 0:
                    errors.append("Empty CSV file")
        
        except Exception as e:
            errors.append(f"File reading error: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            format_type='csv',
            errors=errors,
            warnings=warnings,
            metadata=metadata
        )
    
    def _validate_json_structure(self, data: Dict[str, Any], line_num: int, 
                                errors: List[str], warnings: List[str]) -> None:
        """验证JSON对象结构
        
        Args:
            data: JSON对象
            line_num: 行号
            errors: 错误列表
            warnings: 警告列表
        """
        # 检查事件对象
        if 'event_id' in data or 'title' in data:
            # 事件对象验证
            if 'event_id' not in data:
                errors.append(f"Line {line_num}: Event missing 'event_id' field")
            if 'title' not in data and 'description' not in data:
                warnings.append(f"Line {line_num}: Event missing both 'title' and 'description' fields")
        
        # 检查关系对象
        elif 'source_event_id' in data and 'target_event_id' in data:
            # 关系对象验证
            required_fields = ['source_event_id', 'target_event_id', 'relation_type']
            for field in required_fields:
                if field not in data:
                    errors.append(f"Line {line_num}: Relation missing '{field}' field")
            
            # 检查置信度
            if 'confidence' in data:
                confidence = data['confidence']
                if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
                    warnings.append(f"Line {line_num}: Invalid confidence value: {confidence}")
        
        # 检查时间戳格式
        timestamp_fields = ['timestamp', 'created_at', 'updated_at']
        for field in timestamp_fields:
            if field in data:
                timestamp = data[field]
                if isinstance(timestamp, str):
                    # 尝试解析ISO格式时间戳
                    try:
                        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except ValueError:
                        warnings.append(f"Line {line_num}: Invalid timestamp format in '{field}': {timestamp}")
    
    def validate_batch(self, file_paths: List[Union[str, Path]]) -> Dict[str, ValidationResult]:
        """批量验证文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            Dict[str, ValidationResult]: 文件路径到验证结果的映射
        """
        results = {}
        for file_path in file_paths:
            file_path = Path(file_path)
            results[str(file_path)] = self.validate_file(file_path)
        return results
    
    def generate_validation_report(self, results: Dict[str, ValidationResult], 
                                 output_file: Optional[str] = None) -> str:
        """生成验证报告
        
        Args:
            results: 验证结果字典
            output_file: 输出文件路径
            
        Returns:
            str: 报告内容
        """
        report_lines = []
        report_lines.append("# File Format Validation Report")
        report_lines.append(f"Generated at: {datetime.now().isoformat()}")
        report_lines.append("")
        
        total_files = len(results)
        valid_files = sum(1 for r in results.values() if r.is_valid)
        
        report_lines.append(f"## Summary")
        report_lines.append(f"- Total files: {total_files}")
        report_lines.append(f"- Valid files: {valid_files}")
        report_lines.append(f"- Invalid files: {total_files - valid_files}")
        report_lines.append("")
        
        for file_path, result in results.items():
            report_lines.append(f"## {Path(file_path).name}")
            report_lines.append(f"- **Path**: {file_path}")
            report_lines.append(f"- **Format**: {result.format_type}")
            report_lines.append(f"- **Valid**: {'✅' if result.is_valid else '❌'}")
            
            if result.metadata:
                report_lines.append(f"- **Metadata**:")
                for key, value in result.metadata.items():
                    report_lines.append(f"  - {key}: {value}")
            
            if result.errors:
                report_lines.append(f"- **Errors**:")
                for error in result.errors:
                    report_lines.append(f"  - {error}")
            
            if result.warnings:
                report_lines.append(f"- **Warnings**:")
                for warning in result.warnings:
                    report_lines.append(f"  - {warning}")
            
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
        
        return report_content