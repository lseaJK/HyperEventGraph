import os
import pandas as pd
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import json

def merge_data():
    # 初始化一个空列表来存储所有“简述”内容
    data = []

    # 获取当前文件夹下的所有文件
    current_directory = os.getcwd()
    files = os.listdir(current_directory)

    # 遍历文件列表，查找Excel文件并读取“简述”列
    for file in files:
        if file.endswith('.xlsx'):  # 检查文件是否为Excel文件
            file_path = os.path.join(current_directory, file)  # 获取文件的完整路径
            try:
                df = pd.read_excel(file_path)  # 读取Excel文件
                if '简述' in df.columns:  # 检查“简述”列是否存在
                    brief_list = df['简述'].tolist()  # 获取“简述”列的内容并转换为列表
                    data.extend(brief_list)  # 将内容添加到data列表中
            except Exception as e:
                print(f"Error reading {file}: {e}")

    print(f"Total items before filtering: {len(data)}")
    return data

def filter_data(data):
    # 去重后的列表
    filtered_data = []

    # 遍历数据列表，过滤掉相似度超过60%的文本
    for item in data:
        if not any(fuzz.ratio(item, existing_item) > 60 for existing_item in filtered_data):
            filtered_data.append(item)

    print(f"Total items after filtering: {len(filtered_data)}")
    return filtered_data

def save_to_json(filtered_data):
    # 将去重后的列表转化为JSON格式
    filtered_data_json = json.dumps(filtered_data, ensure_ascii=False, indent=4)

    # 将JSON数据写入文件
    with open('filtered_data.json', 'w', encoding='utf-8') as json_file:
        json_file.write(filtered_data_json)

    print("去重后的数据已成功写入到 filtered_data.json 文件中")

    
def extract_demo_data():
    try:
        # 读取filtered_data.json文件
        with open('filtered_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)

        # 取前1000行
        demo_data = data[:5]

        # 将前1000行数据写入filtered_data_demo.json文件
        with open('filtered_data_demo.json', 'w', encoding='utf-8') as demo_json_file:
            json.dump(demo_data, demo_json_file, ensure_ascii=False, indent=4)

        print("已成功从filtered_data.json提取前1000行数据并保存到filtered_data_demo.json文件中")
    except Exception as e:
        print(f"提取数据时出错：{e}")

        
def main():
    # 合并数据
    data = merge_data()
    
    # 过滤数据
    filtered_data = filter_data(data)
    
    # 保存到JSON文件
    save_to_json(filtered_data)

if __name__ == "__main__":
#     main()
    extract_demo_data()
    pass
    