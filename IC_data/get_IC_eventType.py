import os
import json
import requests
from typing import List, Dict

# ====== 通用配置 ======
# API_KEY = os.getenv("SILICONFLOW_API_KEY")  # 建议写到环境变量
API_KEY = "sk-gyfzsxbiliybpcqteeuhdykexrfindhmuhwheuamasqqvdym"
BATCH_SIZE = 20                            # 每次请求 20 条
RESULT_FILE = "deepseek_results.jsonl"     # 追加写结果
PROMPT_PREFIX = """你是一个专门用于集成电路（IC）行业事件抽取的智能助手，任务是从输入的新闻文本中识别和提取**事件类型**，用于构建**事理图谱中的事件概念层标签**。

### 🧠 背景说明：

在事理图谱构建过程中，事件类型（Event Type）用于对新闻文本中发生的事件进行高层次、**细粒度且语义清晰的分类标注**。每个事件类型应代表一个抽象但具体的事件概念，如“价格调整”、“合作签署”等。避免使用模糊或过于宽泛的标签（如“商业事件”或“市场动态”）。

### 🎯 任务目标：

从一组IC领域的新闻文本中，归纳并输出所有唯一的、具体的**事件类型标签**，以中文为主，输出格式为 JSON 数组。

### 📥 输入说明：

- 输入是一组与集成电路产业相关的新闻文本，每条为一个段落或句子。
  
- 每条文本可能包含：时间、主体（如公司、政府机构）、行为（如合作、研发、融资等）以及影响或结果。

### 📤 输出要求：

- 输出一个 JSON 数组，每个元素为一个具体、唯一的**事件类型标签**（优先使用中文）。
  
- 每个标签应：
  
  - 精炼具体，长度建议不超过10个汉字；
    
  - 表示一个抽象但可识别的事件类型；
    
  - 不包含特定公司名、数字或非类型性内容。
    
- 输出仅包括事件类型标签，不输出事件原文或其他解释性内容。
  

```json
["事件类型1", "事件类型2", "事件类型3", ...]
```

### ✅ 执行步骤（内部处理逻辑，无需输出）：

1. **事件识别**：提取每条文本的关键要素（主体、行为、对象、影响等）。
  
2. **类型归类**：将每个事件归入最贴切的细粒度类型标签。
  
3. **同义合并**：将语义接近的事件（如“降价”、“价格下调”）统一为一个标准类型（如“价格调整”）。
  
4. **去重整理**：输出唯一、完整、无遗漏的事件类型集合。

---

现在，请基于用户提供的实际文本组，输出事件类型列表。

"""

# ====== 读取 filtered_data ======
def load_filtered_data(path: str = "filtered_data.json") -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ====== 调用 SiliconFlow DeepSeek ======

import requests

url = "https://api.siliconflow.cn/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def ask_deepseek(batch: List[str]) -> str:
    """
    把 20 条文本合并成一条 prompt 发送给 DeepSeek，返回模型回复。
    """
    content = PROMPT_PREFIX + "\n".join(f"{i+1}. {q}" for i, q in enumerate(batch))
#     print(content)
#     exit(0)
    payload = {
        "model": "deepseek-ai/DeepSeek-R1",
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": False
    }
    resp = requests.request("POST", url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

# # ====== 主流程 ======
# def iterate_and_ask():
#     data = load_filtered_data()
#     total = len(data)
#     for start in range(0, total, BATCH_SIZE):
#         end = min(start + BATCH_SIZE, total)
#         batch = data[start:end]
#         print(f"[{start}-{end-1}] 正在请求 DeepSeek …")
#         try:
#             answer = ask_deepseek(batch)
#             result = {
#                 "batch_index": start // BATCH_SIZE,
#                 "questions": batch,
#                 "answer": answer
#             }
#             # 追加写 jsonl
#             with open(RESULT_FILE, "a", encoding="utf-8") as f:
#                 f.write(json.dumps(result, ensure_ascii=False) + "\n")
#             print(f"已写入第 {start//BATCH_SIZE} 批结果")
#             break
#         except Exception as e:
#             print(f"第 {start//BATCH_SIZE} 批出错：{e}")
#             continue

# if __name__ == "__main__":
#     # 保证不会重复写入，可先清空结果文件
#     if os.path.exists(RESULT_FILE):
#         os.remove(RESULT_FILE)
#     iterate_and_ask()
    
import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

BATCH_SIZE = 10
NUM_WORKERS = 10
RETRY_WORKERS = 5
RESULT_FILE = "result.jsonl"
LOCK = threading.Lock()


# 放在文件头部
from ratelimit import limits, sleep_and_retry
RPM = 1000            # 每分钟最多 1000 次

# 把真正的请求函数再包一层
@sleep_and_retry
@limits(calls=RPM, period=60)
def ask_deepseek_rl(batch):
    # 这里还是原来的逻辑，只是名字换一下，方便插入限流
    return ask_deepseek(batch)

def read_completed_batches():
    if not os.path.exists(RESULT_FILE):
        return set()
    completed = set()
    with open(RESULT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                completed.add(obj["batch_index"])
            except:
                continue
    return completed

def process_batch(batch_index, data):
    start = batch_index * BATCH_SIZE
    end = min(start + BATCH_SIZE, len(data))
    batch = data[start:end]
    try:
        print(f"[{start}-{end - 1}] 正在请求 DeepSeek …")
        answer = ask_deepseek_rl(batch)
        result = {
            "batch_index": batch_index,
#             "questions": batch,
            "answer": answer
        }
        with LOCK:
            with open(RESULT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(f"✅ 已写入第 {batch_index} 批结果")
        return True
    except Exception as e:
        print(f"❌ 第 {batch_index} 批出错：{e}")
        return False

def run_batches(batch_indices, data, num_workers):
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for idx in batch_indices:
            futures.append(executor.submit(process_batch, idx, data))
        # 等待所有任务完成
        results = [f.result() for f in tqdm(futures, desc="执行批次")]
    return results

def main():
    data = load_filtered_data()
    total_batches = (len(data) + BATCH_SIZE - 1) // BATCH_SIZE

    # 读取已经完成的批次
    completed_batches = read_completed_batches()
    all_batches = set(range(total_batches))
    remaining_batches = sorted(all_batches - completed_batches)

    print(f"📌 总批次：{total_batches}，已完成：{len(completed_batches)}，待处理：{len(remaining_batches)}")

    # 第一轮并发执行
    if remaining_batches:
        print(f"🚀 开始第一轮并发执行 {len(remaining_batches)} 批")
        run_batches(remaining_batches, data, NUM_WORKERS)

    # 检查是否仍有未完成的批次
    completed_batches = read_completed_batches()
    remaining_batches = sorted(all_batches - completed_batches)

    if remaining_batches:
        print(f"⚠️ 第二轮重试未完成的 {len(remaining_batches)} 批")
        run_batches(remaining_batches, data, RETRY_WORKERS)

    # 最终检查
    completed_batches = read_completed_batches()
    remaining_batches = sorted(all_batches - completed_batches)

    if not remaining_batches:
        print("🎉 所有批次执行完毕")
    else:
        print(f"❗ 仍有未完成的批次：{remaining_batches}")

if __name__ == "__main__":
    main()
