# src/agents/toolkits/schema_learning_toolkit.py

import json
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import ollama

class SchemaLearningToolkit:
    """
    包含Schema学习所需工具的工具包，例如事件聚类和Schema归纳。
    """

    def __init__(self, n_clusters: int = 5, llm_client=None):
        """
        初始化工具包。

        Args:
            n_clusters (int): 聚类算法的目标簇数。
            llm_client: 用于与LLM交互的客户端，遵循与autogen兼容的接口。
        """
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.clusterer = KMeans(n_clusters=self.n_clusters, random_state=42)
        self.llm_client = llm_client or self._default_llm_client

    def _default_llm_client(self, prompt: str) -> str:
        """
        一个默认的LLM客户端，如果外部没有提供，则使用Ollama。
        """
        try:
            response = ollama.chat(
                model='qwen2.5:14b', # 假设这是在Ollama中可用的模型
                messages=[{'role': 'user', 'content': prompt}],
                stream=False
            )
            return response['message']['content']
        except Exception as e:
            print(f"[SchemaLearningToolkit Error] Ollama request failed: {e}")
            return "{}" # 返回一个空的JSON对象字符串

    def cluster_events(self, event_texts: List[str]) -> Dict[int, List[str]]:
        """
        将一组事件文本聚类成不同的组。

        Args:
            event_texts (List[str]): 未知事件的文本描述列表。

        Returns:
            Dict[int, List[str]]: 一个字典，键是簇ID，值是该簇中的事件文本列表。
        """
        if not event_texts or len(event_texts) < self.n_clusters:
            # 如果文本太少，无法进行有意义的聚类，则将所有文本归为一类
            return {0: event_texts}

        vectors = self.vectorizer.fit_transform(event_texts)
        self.clusterer.fit(vectors)
        
        clusters: Dict[int, List[str]] = {i: [] for i in range(self.n_clusters)}
        for i, label in enumerate(self.clusterer.labels_):
            clusters[int(label)].append(event_texts[i])
            
        return clusters

    def induce_schema(self, event_cluster: List[str]) -> Dict[str, Any]:
        """
        从一个事件簇中归纳出新的JSON Schema。

        Args:
            event_cluster (List[str]): 来自同一簇的一组事件文本。

        Returns:
            Dict[str, Any]: 一个代表新事件类型的JSON Schema。
        """
        if not event_cluster:
            return {}

        prompt = f"""
You are an expert in data modeling and schema design.
Based on the following event descriptions, which are all of the same unknown type, please induce a generic JSON Schema that can describe them.

CRITICAL INSTRUCTIONS:
1.  Analyze the common entities, attributes, and relationships in these texts.
2.  Create a JSON Schema with a clear `title`, a `description`, and a `properties` object.
3.  The schema should be general enough to cover all examples but specific enough to be useful.
4.  Your output MUST be ONLY a valid JSON object representing the schema. Do not include any other text or formatting.

EVENT EXAMPLES:
---
{json.dumps(event_cluster, indent=2, ensure_ascii=False)}
---

Now, provide the JSON Schema.
"""
        
        response_text = self.llm_client(prompt)
        
        try:
            # 确保返回的是有效的JSON
            return json.loads(response_text)
        except json.JSONDecodeError:
            print(f"[SchemaLearningToolkit Error] Failed to parse LLM response into JSON: {response_text}")
            return {"error": "Failed to induce schema from LLM response."}

if __name__ == '__main__':
    # 示例用法
    toolkit = SchemaLearningToolkit(n_clusters=2)
    
    # 示例文本
    unknown_events = [
        "Global Tech Inc. announced a strategic partnership with Future AI LLC to co-develop a new AI platform.",
        "The CEO of Innovate Corp revealed a joint venture with Visionary Systems to build a next-gen data center.",
        "Apple is rumored to be in talks with a smaller firm, AudioPro, for a potential collaboration on new speaker technology.",
        "Samsung's quarterly earnings report shows a 15% increase in profit, largely driven by their semiconductor division.",
        "Intel released its financial statements, indicating a slight downturn in revenue but strong growth in its data center group."
    ]
    
    # 1. 聚类
    clusters = toolkit.cluster_events(unknown_events)
    print("--- Clusters Found ---")
    print(json.dumps(clusters, indent=2, ensure_ascii=False))
    
    # 2. 为第一个簇归纳Schema
    if clusters and clusters.get(0):
        print("\n--- Inducing Schema for Cluster 0 ---")
        induced_schema = toolkit.induce_schema(clusters[0])
        print(json.dumps(induced_schema, indent=2, ensure_ascii=False))

