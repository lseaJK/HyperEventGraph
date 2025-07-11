import os
from hypergraphrag import HyperGraphRAG
os.environ["OPENAI_API_KEY"]="sk-eb26a5a560d74d308ac772be37b2bc15"

rag = HyperGraphRAG(working_dir=f"expr/example")

# query_text = '美三大芯片巨头首席执行官在华盛顿举行会谈时向拜登政府官员提出了什么建议?'
# query_text = '除了台积电外，其他晶圆代工厂降价的形式有哪些？'
query_text = '现阶段晶圆代工厂成熟制程产能利用率低的主要原因是什么？'

result = rag.query(query_text)
print(result)