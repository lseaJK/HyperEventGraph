import re, json, csv

input_file = "neo4j_heg_export.txt"
output_file = "neo4j_node_data.csv"
entity_count = 3

field_list = [
    'label',
    'eventId',
    'event_type',
    'micro_event_type',
    'event_date',
    'description',
    'text',
    'quantitative_data',
    'involved_entities',
]
for i in range(1, entity_count + 1):
    field_list += [f'entity_name_{i}', f'entity_type_{i}', f'role_in_event_{i}']

event_pattern = re.compile(r'\(:Event\s*\{(.*?)\}\)', re.DOTALL)
rows = []

def parse_props(props_str):
    props = {}
    i, n = 0, len(props_str)
    while i < n:
        while i < n and props_str[i].isspace():
            i += 1
        key_start = i
        while i < n and props_str[i] != ':':
            i += 1
        key = props_str[key_start:i].strip()
        i += 1
        while i < n and props_str[i].isspace():
            i += 1
        if i >= n:
            break
        if props_str[i] in '"\'':
            quote = props_str[i]
            val_start = i
            i += 1
            while i < n:
                if props_str[i] == quote and props_str[i-1] != '\\':
                    break
                i += 1
            i += 1
            value = props_str[val_start:i].strip()
        elif props_str[i] in '[{':
            open_char = props_str[i]
            close_char = ']' if open_char == '[' else '}'
            val_start = i
            depth = 1
            i += 1
            while i < n and depth > 0:
                if props_str[i] == open_char:
                    depth += 1
                elif props_str[i] == close_char:
                    depth -= 1
                i += 1
            value = props_str[val_start:i].strip()
        else:
            val_start = i
            while i < n and props_str[i] != ',':
                i += 1
            value = props_str[val_start:i].strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        props[key] = value
        while i < n and (props_str[i] == ',' or props_str[i].isspace()):
            i += 1
    return props

def parse_entities(cell, max_entities=entity_count):
    entities = []
    # 1. 尝试标准json解析
    try:
        if cell and cell.startswith('['):
            entities = json.loads(cell)
    except Exception:
        pass
    # 2. 如果json失败，尝试去除多余转义再json
    if not entities:
        try:
            cell2 = cell.replace('\\"', '"').replace('\"', '"')
            entities = json.loads(cell2)
        except Exception:
            pass
    # 3. 如果还失败，用正则表达式
    if not entities:
        # 兼容各种分隔符和转义
        entity_pattern = re.compile(r'entity_name"?:\s*"(.*?)".*?entity_type"?:\s*"(.*?)".*?role_in_event"?:\s*"(.*?)"', re.DOTALL)
        for m in entity_pattern.finditer(cell):
            entities.append({
                'entity_name': m.group(1),
                'entity_type': m.group(2),
                'role_in_event': m.group(3)
            })
    parsed = []
    for i in range(max_entities):
        if i < len(entities):
            e = entities[i]
            parsed.extend([
                e.get('entity_name', ''),
                e.get('entity_type', ''),
                e.get('role_in_event', '')
            ])
        else:
            parsed.extend(['', '', ''])
    return parsed

with open(input_file, 'r', encoding='utf-8') as f:
    for line in f:
        match = event_pattern.search(line)
        if match:
            props_str = match.group(1)
            props = parse_props(props_str)
            row = {k: '' for k in field_list}
            row['label'] = 'Event'
            row['eventId'] = props.get('eventId', props.get('event_id', ''))
            row['event_type'] = props.get('event_type', '')
            row['micro_event_type'] = props.get('micro_event_type', '')
            row['event_date'] = props.get('event_date', '')
            row['description'] = props.get('description', '')
            row['text'] = props.get('text', '')
            row['quantitative_data'] = props.get('quantitative_data', '')
            row['involved_entities'] = props.get('involved_entities', '')
            # 统一用parse_entities函数提取实体信息
            entities = parse_entities(row['involved_entities'])
            for i in range(1, entity_count + 1):
                idx = (i-1)*3
                row[f'entity_name_{i}'] = entities[idx] if idx < len(entities) else ''
                row[f'entity_type_{i}'] = entities[idx+1] if idx+1 < len(entities) else ''
                row[f'role_in_event_{i}'] = entities[idx+2] if idx+2 < len(entities) else ''
            rows.append(row)

with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=field_list)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

print(f"处理完成！输出文件: {output_file}")
