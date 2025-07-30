# 初步事件抽取数据质量分析报告

### 1. 数据完整性校验
- 总记录数: 5313
  - `event_date`: 3154 (59.36%)
  - `quantitative_data`: 5313 (100.00%)
  - `forecast`: 5313 (100.00%)
  - `quantitative_data.metric`: 3460 (65.12%)
  - `quantitative_data.value`: 3990 (75.10%)
  - `quantitative_data.unit`: 3527 (66.38%)
  - `quantitative_data.change_rate`: 4534 (85.34%)
  - `quantitative_data.period`: 4409 (82.99%)

### 2. 事件类型分布
- 各事件类型计数:
  - `MarketAction`: 2538
  - `Other`: 1017
  - `Partnership`: 628
  - `SupplyChainDisruption`: 524
  - `LegalRegulation`: 243
  - `PolicyChange`: 240
  - `ExecutiveChange`: 119
  - `CapacityChange`: 3
  - `TechnologyDevelopment`: 1


### 3. 核心实体分析
  - `华为`: 337
  - `苹果`: 129
  - `台积电`: 92
  - `英伟达`: 62
  - `三星`: 51
  - `荣耀`: 48
  - `三星电子`: 46
  - `英特尔`: 44
  - `小米`: 37
  - `苹果公司`: 36
  - `工信部`: 35
  - `中芯国际`: 34
  - `公司`: 31
  - `华为技术有限公司`: 29
  - `腾讯`: 29
  - `兆易创新`: 28
  - `阿里巴巴`: 28
  - `联发科`: 28
  - `微软`: 28
  - `字节跳动`: 27
  - `OPPO`: 26
  - `苏宁易购`: 26
  - `闻泰科技`: 26
  - `高通`: 25
  - `中国联通`: 24
  - `百度`: 24
  - `SK海力士`: 24
  - `韦尔股份`: 23
  - `IDC`: 23
  - `京东`: 23
  - `特斯拉`: 21
  - `抖音`: 21
  - `京东方`: 20
  - `芯源微`: 20
  - `中国`: 20
  - `三安光电`: 19
  - `半导体行业`: 19
  - `阿里云`: 19
  - `业内人士`: 18
  - `比亚迪半导体`: 18
  - `北京君正`: 18
  - `中国移动`: 17
  - `爱奇艺`: 17
  - `北方华创`: 17
  - `美国政府`: 17
  - `Canalys`: 17
  - `晶圆代工厂`: 17
  - `Omdia`: 16
  - `寒武纪`: 16
  - `美国`: 16

### 4. 定量数据探查
- `quantitative_data` 字段缺失: 5313 (100.00%)
- 在 quantitative_data 为空的记录中，description 仍包含:
  - `money`: 494 (9.30%)
  - `percentage`: 1056 (19.88%)
  - `date`: 332 (6.25%)
- 通过 description 提取到数值信息并写入 `extracted_quantitative` 的记录数: 1582
