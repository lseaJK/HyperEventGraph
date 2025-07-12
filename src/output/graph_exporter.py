"""图谱导出管理器

实现Neo4j图数据到多种格式的导出功能，支持GraphML、GEXF等可视化格式。
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import json
import csv

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None


class GraphExporter:
    """图谱导出管理器"""
    
    def __init__(self, output_dir: str = "output", neo4j_uri: str = None, 
                 neo4j_user: str = None, neo4j_password: str = None):
        """初始化图谱导出器
        
        Args:
            output_dir: 输出目录路径
            neo4j_uri: Neo4j数据库URI
            neo4j_user: Neo4j用户名
            neo4j_password: Neo4j密码
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        
        if GraphDatabase and all([neo4j_uri, neo4j_user, neo4j_password]):
            try:
                self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            except Exception as e:
                print(f"Failed to connect to Neo4j: {e}")
    
    def __del__(self):
        """析构函数，关闭Neo4j连接"""
        if self.driver:
            self.driver.close()
    
    def export_to_graphml(self, 
                         nodes: List[Dict[str, Any]] = None, 
                         edges: List[Dict[str, Any]] = None,
                         filename: str = None,
                         cypher_query: str = None) -> str:
        """导出为GraphML格式
        
        Args:
            nodes: 节点数据列表
            edges: 边数据列表
            filename: 输出文件名
            cypher_query: 从Neo4j查询数据的Cypher语句
            
        Returns:
            str: 输出文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"graph_{timestamp}.graphml"
            
        # 如果提供了Cypher查询，从Neo4j获取数据
        if cypher_query and self.driver:
            nodes, edges = self._query_neo4j_data(cypher_query)
        
        # 如果仍然没有数据，使用默认查询
        if not nodes and not edges and self.driver:
            nodes, edges = self._get_default_graph_data()
        
        if not nodes and not edges:
            raise ValueError("No graph data provided")
        
        filepath = self.output_dir / filename
        
        # 创建GraphML XML结构
        root = ET.Element("graphml")
        root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:schemaLocation", 
                "http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd")
        
        # 定义属性键
        node_attrs = self._get_node_attributes(nodes or [])
        edge_attrs = self._get_edge_attributes(edges or [])
        
        # 添加节点属性定义
        for attr_id, (attr_name, attr_type) in node_attrs.items():
            key_elem = ET.SubElement(root, "key")
            key_elem.set("id", attr_id)
            key_elem.set("for", "node")
            key_elem.set("attr.name", attr_name)
            key_elem.set("attr.type", attr_type)
        
        # 添加边属性定义
        for attr_id, (attr_name, attr_type) in edge_attrs.items():
            key_elem = ET.SubElement(root, "key")
            key_elem.set("id", attr_id)
            key_elem.set("for", "edge")
            key_elem.set("attr.name", attr_name)
            key_elem.set("attr.type", attr_type)
        
        # 创建图元素
        graph_elem = ET.SubElement(root, "graph")
        graph_elem.set("id", "G")
        graph_elem.set("edgedefault", "directed")
        
        # 添加节点
        if nodes:
            for node in nodes:
                node_elem = ET.SubElement(graph_elem, "node")
                node_elem.set("id", str(node.get('id', node.get('event_id', ''))))
                
                # 添加节点属性
                for key, value in node.items():
                    if key != 'id' and key != 'event_id':
                        attr_id = f"n_{key}"
                        if attr_id in node_attrs:
                            data_elem = ET.SubElement(node_elem, "data")
                            data_elem.set("key", attr_id)
                            data_elem.text = str(value)
        
        # 添加边
        if edges:
            for i, edge in enumerate(edges):
                edge_elem = ET.SubElement(graph_elem, "edge")
                edge_elem.set("id", str(edge.get('id', f'e{i}')))
                edge_elem.set("source", str(edge.get('source', edge.get('source_event_id', ''))))
                edge_elem.set("target", str(edge.get('target', edge.get('target_event_id', ''))))
                
                # 添加边属性
                for key, value in edge.items():
                    if key not in ['id', 'source', 'target', 'source_event_id', 'target_event_id']:
                        attr_id = f"e_{key}"
                        if attr_id in edge_attrs:
                            data_elem = ET.SubElement(edge_elem, "data")
                            data_elem.set("key", attr_id)
                            data_elem.text = str(value)
        
        # 写入文件
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        
        return str(filepath)
    
    def export_to_gexf(self, 
                      nodes: List[Dict[str, Any]] = None, 
                      edges: List[Dict[str, Any]] = None,
                      filename: str = None,
                      cypher_query: str = None) -> str:
        """导出为GEXF格式
        
        Args:
            nodes: 节点数据列表
            edges: 边数据列表
            filename: 输出文件名
            cypher_query: 从Neo4j查询数据的Cypher语句
            
        Returns:
            str: 输出文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"graph_{timestamp}.gexf"
            
        # 如果提供了Cypher查询，从Neo4j获取数据
        if cypher_query and self.driver:
            nodes, edges = self._query_neo4j_data(cypher_query)
        
        # 如果仍然没有数据，使用默认查询
        if not nodes and not edges and self.driver:
            nodes, edges = self._get_default_graph_data()
        
        if not nodes and not edges:
            raise ValueError("No graph data provided")
        
        filepath = self.output_dir / filename
        
        # 创建GEXF XML结构
        root = ET.Element("gexf")
        root.set("xmlns", "http://www.gexf.net/1.2draft")
        root.set("version", "1.2")
        
        # 元数据
        meta = ET.SubElement(root, "meta")
        meta.set("lastmodifieddate", datetime.now().strftime("%Y-%m-%d"))
        
        creator = ET.SubElement(meta, "creator")
        creator.text = "HyperEventGraph"
        
        description = ET.SubElement(meta, "description")
        description.text = "Event graph exported from HyperEventGraph"
        
        # 图元素
        graph_elem = ET.SubElement(root, "graph")
        graph_elem.set("mode", "static")
        graph_elem.set("defaultedgetype", "directed")
        
        # 属性定义
        node_attrs = self._get_node_attributes(nodes or [])
        edge_attrs = self._get_edge_attributes(edges or [])
        
        if node_attrs:
            attributes_elem = ET.SubElement(graph_elem, "attributes")
            attributes_elem.set("class", "node")
            
            for attr_id, (attr_name, attr_type) in node_attrs.items():
                attr_elem = ET.SubElement(attributes_elem, "attribute")
                attr_elem.set("id", attr_id)
                attr_elem.set("title", attr_name)
                attr_elem.set("type", self._convert_to_gexf_type(attr_type))
        
        if edge_attrs:
            attributes_elem = ET.SubElement(graph_elem, "attributes")
            attributes_elem.set("class", "edge")
            
            for attr_id, (attr_name, attr_type) in edge_attrs.items():
                attr_elem = ET.SubElement(attributes_elem, "attribute")
                attr_elem.set("id", attr_id)
                attr_elem.set("title", attr_name)
                attr_elem.set("type", self._convert_to_gexf_type(attr_type))
        
        # 节点
        if nodes:
            nodes_elem = ET.SubElement(graph_elem, "nodes")
            for node in nodes:
                node_elem = ET.SubElement(nodes_elem, "node")
                node_elem.set("id", str(node.get('id', node.get('event_id', ''))))
                node_elem.set("label", str(node.get('title', node.get('description', 'Unknown'))))
                
                # 节点属性
                if len(node) > 2:  # 除了id和label之外还有其他属性
                    attvalues_elem = ET.SubElement(node_elem, "attvalues")
                    for key, value in node.items():
                        if key not in ['id', 'event_id', 'title', 'description']:
                            attr_id = f"n_{key}"
                            if attr_id in node_attrs:
                                attvalue_elem = ET.SubElement(attvalues_elem, "attvalue")
                                attvalue_elem.set("for", attr_id)
                                attvalue_elem.set("value", str(value))
        
        # 边
        if edges:
            edges_elem = ET.SubElement(graph_elem, "edges")
            for i, edge in enumerate(edges):
                edge_elem = ET.SubElement(edges_elem, "edge")
                edge_elem.set("id", str(edge.get('id', f'e{i}')))
                edge_elem.set("source", str(edge.get('source', edge.get('source_event_id', ''))))
                edge_elem.set("target", str(edge.get('target', edge.get('target_event_id', ''))))
                edge_elem.set("label", str(edge.get('relation_type', 'unknown')))
                
                # 边属性
                if len(edge) > 4:  # 除了基本属性之外还有其他属性
                    attvalues_elem = ET.SubElement(edge_elem, "attvalues")
                    for key, value in edge.items():
                        if key not in ['id', 'source', 'target', 'source_event_id', 'target_event_id', 'relation_type']:
                            attr_id = f"e_{key}"
                            if attr_id in edge_attrs:
                                attvalue_elem = ET.SubElement(attvalues_elem, "attvalue")
                                attvalue_elem.set("for", attr_id)
                                attvalue_elem.set("value", str(value))
        
        # 写入文件
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        
        return str(filepath)
    
    def export_to_csv(self, 
                     nodes: List[Dict[str, Any]] = None, 
                     edges: List[Dict[str, Any]] = None,
                     filename_prefix: str = None,
                     cypher_query: str = None) -> Dict[str, str]:
        """导出为CSV格式（节点和边分别导出）
        
        Args:
            nodes: 节点数据列表
            edges: 边数据列表
            filename_prefix: 文件名前缀
            cypher_query: 从Neo4j查询数据的Cypher语句
            
        Returns:
            Dict[str, str]: 包含nodes_file和edges_file路径的字典
        """
        if filename_prefix is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_prefix = f"graph_{timestamp}"
        
        # 如果提供了Cypher查询，从Neo4j获取数据
        if cypher_query and self.driver:
            nodes, edges = self._query_neo4j_data(cypher_query)
        
        # 如果仍然没有数据，使用默认查询
        if not nodes and not edges and self.driver:
            nodes, edges = self._get_default_graph_data()
        
        result = {}
        
        # 导出节点
        if nodes:
            nodes_file = self.output_dir / f"{filename_prefix}_nodes.csv"
            with open(nodes_file, 'w', newline='', encoding='utf-8') as f:
                if nodes:
                    fieldnames = set()
                    for node in nodes:
                        fieldnames.update(node.keys())
                    
                    writer = csv.DictWriter(f, fieldnames=list(fieldnames))
                    writer.writeheader()
                    writer.writerows(nodes)
            
            result['nodes_file'] = str(nodes_file)
        
        # 导出边
        if edges:
            edges_file = self.output_dir / f"{filename_prefix}_edges.csv"
            with open(edges_file, 'w', newline='', encoding='utf-8') as f:
                if edges:
                    fieldnames = set()
                    for edge in edges:
                        fieldnames.update(edge.keys())
                    
                    writer = csv.DictWriter(f, fieldnames=list(fieldnames))
                    writer.writeheader()
                    writer.writerows(edges)
            
            result['edges_file'] = str(edges_file)
        
        return result
    
    def export_to_json(self, 
                      nodes: List[Dict[str, Any]] = None, 
                      edges: List[Dict[str, Any]] = None,
                      filename: str = None,
                      cypher_query: str = None) -> str:
        """导出为JSON格式
        
        Args:
            nodes: 节点数据列表
            edges: 边数据列表
            filename: 输出文件名
            cypher_query: 从Neo4j查询数据的Cypher语句
            
        Returns:
            str: 输出文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"graph_{timestamp}.json"
        
        # 如果提供了Cypher查询，从Neo4j获取数据
        if cypher_query and self.driver:
            nodes, edges = self._query_neo4j_data(cypher_query)
        
        # 如果仍然没有数据，使用默认查询
        if not nodes and not edges and self.driver:
            nodes, edges = self._get_default_graph_data()
        
        filepath = self.output_dir / filename
        
        graph_data = {
            'nodes': nodes or [],
            'edges': edges or [],
            'metadata': {
                'exported_at': datetime.now().isoformat(),
                'node_count': len(nodes) if nodes else 0,
                'edge_count': len(edges) if edges else 0
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def _query_neo4j_data(self, cypher_query: str) -> tuple:
        """从Neo4j查询数据
        
        Args:
            cypher_query: Cypher查询语句
            
        Returns:
            tuple: (nodes, edges)
        """
        if not self.driver:
            return [], []
        
        nodes = []
        edges = []
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher_query)
                for record in result:
                    # 处理节点
                    for key, value in record.items():
                        if hasattr(value, 'labels'):  # Neo4j节点
                            node_dict = dict(value)
                            node_dict['id'] = value.id
                            node_dict['labels'] = list(value.labels)
                            nodes.append(node_dict)
                        elif hasattr(value, 'type'):  # Neo4j关系
                            edge_dict = dict(value)
                            edge_dict['id'] = value.id
                            edge_dict['source'] = value.start_node.id
                            edge_dict['target'] = value.end_node.id
                            edge_dict['type'] = value.type
                            edges.append(edge_dict)
        except Exception as e:
            print(f"Error querying Neo4j: {e}")
        
        return nodes, edges
    
    def _get_default_graph_data(self) -> tuple:
        """获取默认的图数据
        
        Returns:
            tuple: (nodes, edges)
        """
        default_query = """
        MATCH (n)-[r]->(m)
        RETURN n, r, m
        LIMIT 1000
        """
        return self._query_neo4j_data(default_query)
    
    def _get_node_attributes(self, nodes: List[Dict[str, Any]]) -> Dict[str, tuple]:
        """获取节点属性定义
        
        Args:
            nodes: 节点列表
            
        Returns:
            Dict[str, tuple]: 属性ID到(属性名, 属性类型)的映射
        """
        attrs = {}
        for node in nodes:
            for key, value in node.items():
                if key not in ['id', 'event_id']:
                    attr_id = f"n_{key}"
                    attr_type = self._infer_type(value)
                    attrs[attr_id] = (key, attr_type)
        return attrs
    
    def _get_edge_attributes(self, edges: List[Dict[str, Any]]) -> Dict[str, tuple]:
        """获取边属性定义
        
        Args:
            edges: 边列表
            
        Returns:
            Dict[str, tuple]: 属性ID到(属性名, 属性类型)的映射
        """
        attrs = {}
        for edge in edges:
            for key, value in edge.items():
                if key not in ['id', 'source', 'target', 'source_event_id', 'target_event_id']:
                    attr_id = f"e_{key}"
                    attr_type = self._infer_type(value)
                    attrs[attr_id] = (key, attr_type)
        return attrs
    
    def _infer_type(self, value: Any) -> str:
        """推断值的类型
        
        Args:
            value: 值
            
        Returns:
            str: 类型字符串
        """
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "double"
        else:
            return "string"
    
    def _convert_to_gexf_type(self, graphml_type: str) -> str:
        """将GraphML类型转换为GEXF类型
        
        Args:
            graphml_type: GraphML类型
            
        Returns:
            str: GEXF类型
        """
        type_mapping = {
            "boolean": "boolean",
            "int": "integer",
            "double": "double",
            "string": "string"
        }
        return type_mapping.get(graphml_type, "string")
    
    def list_export_files(self) -> List[str]:
        """列出所有导出文件
        
        Returns:
            List[str]: 导出文件名列表
        """
        if not self.output_dir.exists():
            return []
        
        extensions = ['.graphml', '.gexf', '.json', '.csv']
        files = []
        for ext in extensions:
            files.extend([f.name for f in self.output_dir.glob(f'*{ext}')])
        
        return sorted(files)