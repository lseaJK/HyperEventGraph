import json
import argparse
import os
import asyncio
from hypergraphrag import HyperGraphRAG, QueryParam
from tqdm.asyncio import tqdm_asyncio

os.environ["OPENAI_API_KEY"] = open("openai_api_key.txt").read().strip()

parser = argparse.ArgumentParser()
parser.add_argument('--data_source', default='hypertension')
args = parser.parse_args()
data_source = args.data_source

rag = HyperGraphRAG(working_dir=f"expr/{data_source}")

async def query_with_semaphore(sem, q):
    async with sem:
        return await rag.aquery(q, QueryParam(only_need_context=True))

async def main():
    with open(f"datasets/{data_source}/questions.json") as f:
        data = json.load(f)
    questions = [item['question'] for item in data]

    sem = asyncio.Semaphore(32)
    tasks = [query_with_semaphore(sem, q) for q in questions]
    results = await tqdm_asyncio.gather(*tasks)

    for d, res in zip(data, results):
        d['knowledge'] = res

    save_dir = f"results/HyperGraphRAG/{data_source}/test_knowledge.json"
    if os.path.exists(save_dir):
        os.remove(save_dir)
    if not os.path.exists(os.path.dirname(save_dir)):
        os.makedirs(os.path.dirname(save_dir))

    with open(save_dir, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Results saved to {save_dir}")

if __name__ == "__main__":
    asyncio.run(main())