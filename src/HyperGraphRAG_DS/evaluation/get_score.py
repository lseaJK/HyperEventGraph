import json
import os
from eval import cal_em, cal_f1
from eval_r import cal_rsim
from eval_g import cal_gen
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import argparse
import os
import json
import traceback
from tqdm import tqdm
from eval import cal_em, cal_f1
from eval_r import cal_rsim
from eval_g import cal_gen
from concurrent.futures import ThreadPoolExecutor


def evaluate_one(d):
    try:
        generation = d['generation']
        try:
            answer = generation.split("<answer>")[1].split("</answer>")[0].strip()
        except:
            answer = generation
        em_score = cal_em([d['golden_answers']], [answer])
        f1_score = cal_f1([d['golden_answers']], [answer])

        # 去重 context
        context = []
        for c in d['context']:
            if c not in context:
                context.append(c)

        rsim_score = cal_rsim(['\n'.join(context)], [d['knowledge']]) if d['knowledge'] != "" else 0.0 
        gen_score = cal_gen(d['question'], d['golden_answers'], generation, f1_score)

        d['em'] = em_score
        d['f1'] = f1_score
        d['rsim'] = rsim_score
        d['gen'] = gen_score["score"]
        d['gen_exp'] = gen_score["explanation"]

        return d
    except Exception as e:
        print(f"[ERROR] Failed processing sample: {d.get('question', 'N/A')}")
        traceback.print_exc()
        raise

def evaluate_method(args):
    method = args.method
    data_source = args.data_source
    success_flag = False  # 控制是否成功保存

    try:
        print(f"[DEBUG] Evaluating {method} on {data_source}")
        data_dir = f"results/{method}/{data_source}/test_generation.json"
        
        if not os.path.exists(data_dir):
            raise FileNotFoundError(f"File not found: {data_dir}")

        with open(data_dir) as f:
            data = json.load(f)

        # 并行处理样本
        max_workers = 64
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            data = list(tqdm(executor.map(evaluate_one, data), total=len(data), desc=method))

        # 汇总指标
        overall_em = sum([d['em'] for d in data]) / len(data)
        overall_f1 = sum([d['f1'] for d in data]) / len(data)
        overall_rsim = sum([d['rsim'] for d in data]) / len(data)
        overall_gen = sum([d['gen'] for d in data]) / len(data)

        print(f"{method} Overall EM: {overall_em:.4f}")
        print(f"{method} Overall F1: {overall_f1:.4f}")
        print(f"{method} Overall R-Sim: {overall_rsim:.4f}")
        print(f"{method} Overall Gen: {overall_gen:.4f}")

        save_base = f"results/{method}/{data_source}"
        os.makedirs(save_base, exist_ok=True)

        result_path = os.path.join(save_base, "test_result.json")
        with open(result_path, 'w') as f:
            json.dump(data, f, indent=4)

        score_path = os.path.join(save_base, "test_score.json")
        with open(score_path, 'w') as f:
            json.dump({
                "overall_em": overall_em,
                "overall_f1": overall_f1,
                "overall_rsim": overall_rsim,
                "overall_gen": overall_gen,
            }, f, indent=4)

        # 成功保存标志
        success_flag = True
        print(f"[SAVED] {result_path}")
        print(f"[SAVED] {score_path}")
        print(f"[SUCCESS] {method} finished and saved.")

    except Exception as e:
        print(f"\n[ERROR] {method} failed due to: {str(e)}")
        traceback.print_exc()
        raise

    if not success_flag:
        raise RuntimeError(f"{method} did not complete saving.")
    
    return True

if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument('--method', type=str, default='HyperGraphRAG_wo_ER')
    parse.add_argument('--data_source', type=str, default='hypertension')
    args = parse.parse_args()
    evaluate_method(args)