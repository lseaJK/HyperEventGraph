

import csv, re, json, ast

infile = 'neo4j_heg_export.cypher'
outfile = 'events.csv'

# 1. 读取 cypher 文件，提取所有 Event 节点
event_pattern = re.compile(r'\(:Event\s*\{(.*?)\}\)', re.DOTALL)
events = []

def parse_props(props_str):
	props = {}
	i = 0
	n = len(props_str)
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
		# 去除首尾引号
		if value.startswith('"') and value.endswith('"'):
			value = value[1:-1]
		elif value.startswith("'") and value.endswith("'"):
			value = value[1:-1]
		# 自动补 involved_entities 的引号
		if key == 'involved_entities':
			v = value
			if not (v.startswith('[') and v.endswith(']')):
				# 可能缺少引号，尝试补全
				if not (v.startswith('"') or v.startswith("'")):
					v = '"' + v + '"'
			value = v
		props[key] = value
		while i < n and (props_str[i] == ',' or props_str[i].isspace()):
			i += 1
	return props

with open(infile, 'r', encoding='utf-8') as f:
	for line in f:
		match = event_pattern.search(line)
		if match:
			props_str = match.group(1)
			props = parse_props(props_str)
			events.append(props)

# 2. 设定语义化表头
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
]
for i in range(1, entity_count+1):
	field_list += [f'entity{i}_name', f'entity{i}_type', f'entity{i}_role']

# 3. 写入 CSV 文件
with open(outfile, 'w', encoding='utf-8', newline='') as f:
	writer = csv.DictWriter(f, fieldnames=field_list)
	writer.writeheader()
	for event in events:
		row = {k: '' for k in field_list}
		row['label'] = 'Event'
		row['eventId'] = event.get('eventId', event.get('event_id', ''))
		row['event_type'] = event.get('event_type', '')
		row['micro_event_type'] = event.get('micro_event_type', '')
		row['event_date'] = event.get('event_date', '')
		row['description'] = event.get('description', '')
		row['text'] = event.get('text', '')
		row['quantitative_data'] = event.get('quantitative_data', '')
		# 解析 involved_entities 字段
		entities = []
		involved_entities = event.get('involved_entities', '')
		if involved_entities:
			# 优先尝试json解析
			try:
				entities = json.loads(involved_entities)
			except Exception:
				# 尝试ast解析
				try:
					entities = ast.literal_eval(involved_entities)
				except Exception:
					# 最后用正则提取
					entities = []
					entity_pattern = re.compile(r'entity_name":\s*"(.*?)".*?entity_type":\s*"(.*?)".*?role_in_event":\s*"(.*?)"')
					for m in entity_pattern.finditer(involved_entities):
						entities.append({
							'entity_name': m.group(1),
							'entity_type': m.group(2),
							'role_in_event': m.group(3)
						})
		for idx in range(entity_count):
			if idx < len(entities):
				ent = entities[idx]
				row[f'entity{idx+1}_name'] = ent.get('entity_name', '')
				row[f'entity{idx+1}_type'] = ent.get('entity_type', '')
				row[f'entity{idx+1}_role'] = ent.get('role_in_event', '')
		writer.writerow(row)
