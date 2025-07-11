import os
import json
from hypergraphrag import HyperGraphRAG
from hypergraphrag.llm import deepseek_v3_complete
import asyncio

os.environ["OPENAI_API_KEY"]="sk-eb26a5a560d74d308ac772be37b2bc15"

rag = HyperGraphRAG(working_dir=f"expr/example")

with open(f"IC_data/filtered_data_demo.json", mode="r") as f:
    unique_contexts = json.load(f)
    
rag.insert(unique_contexts)



if __name__ == "__main__":

#     async def test_embedding():
#         rag = HyperGraphRAG()
#         texts = ["你好", "这是测试"]
#         embeddings = await rag.embedding_func(texts)
#         print("Embeddings:", embeddings)

#     asyncio.run(test_embedding())
    
#     async def main():
#         # 测试文本生成
#         result = await deepseek_v3_complete("How are you?")
#         print("DeepSeek Output:", result)

#     # 异步运行测试
#     asyncio.run(main())
    pass