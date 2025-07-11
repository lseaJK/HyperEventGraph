import os
import argparse
import copy

parse = argparse.ArgumentParser()
parse.add_argument('--method', default='NaiveGeneration')
parse.add_argument('--data_source', default='hypertension')
args = parse.parse_args()
method = args.method
data_source = args.data_source
import json

print(f"Data Source: {data_source}, Method: {method}")

with open(f"results/{method}/{data_source}/test_score.json") as f:
    config = json.load(f)
    
with open(f"results/{method}/{data_source}/test_result.json") as f:
    data = json.load(f)

score_dictr1 = {
    "b": [],
    "n": [],
}

score_dictr ={
    # "em": copy.deepcopy(score_dictr1),
    "f1": copy.deepcopy(score_dictr1),
    "rsim": copy.deepcopy(score_dictr1),
    "gen": copy.deepcopy(score_dictr1)
}
    
for d in data:
    if d["nary"] == 2:
        for key in score_dictr.keys():
            score_dictr[key]["b"].append(d[key])
    elif d["nary"] > 2:
        for key in score_dictr.keys():
            score_dictr[key]["n"].append(d[key])
            
for key in score_dictr.keys():
    for k in score_dictr[key].keys():
        if len(score_dictr[key][k]) == 0:
            score_dictr[key][k] = 0
        else:
            score_dictr[key][k] = sum(score_dictr[key][k]) / len(score_dictr[key][k])
print("Score Dictionary:")

for key in score_dictr1:
    print(key)
    for k in score_dictr.keys():
        print(k, round(score_dictr[k][key]*100,2))
    print("=====================================")

print("overall")
for key in config.keys():
    if key != "overall_em":
        print(key, round(config[key]*100,2))
print("=====================================")

    
