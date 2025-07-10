# 基于超关系图的事理图谱构建方法——架构文档

## 一、 任务目标

构建一个基于超关系图（HyperGraph）的事理图谱（Causal Knowledge Graph）构建方法。该方法利用`HyperGraphRAG`作为核心，并结合自定义的事件Schema，旨在从非结构化和半结构化文本（特别是金融和集成电路领域）中，高效地抽取出事件及其内在联系，并以超图的形式进行存储和查询。

## 二、 核心组件

1.  **HyperGraphRAG**: 作为核心的知识表示和检索增强生成框架。
2.  **事件Schema**: 
    - **金融领域**: 基于金融行业业务本体论 (FIBO) 进行设计。
      - **事件类型**: 
        - `公司并购 (Merger & Acquisition)`: `收购方`, `被收购方`, `交易金额`, `并购状态`, `公告日期`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "公司并购事件",
              "description": "描述一家公司收购另一家公司的事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘公司并购’",
                  "type": "string",
                  "enum": ["公司并购"]
                },
                "acquirer": {
                  "description": "收购方公司",
                  "type": "string"
                },
                "acquired": {
                  "description": "被收购方公司",
                  "type": "string"
                },
                "deal_amount": {
                  "description": "交易金额",
                  "type": "number"
                },
                "status": {
                  "description": "并购状态，如进行中、已完成",
                  "type": "string"
                },
                "announcement_date": {
                  "description": "公告日期",
                  "type": "string",
                  "format": "date"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                }
              },
              "required": ["event_type", "acquirer", "acquired", "announcement_date", "source"]
            }
            ```
        - `投融资 (Investment & Financing)`: `投资方`, `融资方`, `融资金额`, `轮次`, `相关产品`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "投融资事件",
              "description": "描述公司获得投资或进行融资的事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘投融资’",
                  "type": "string",
                  "enum": ["投融资"]
                },
                "investors": {
                  "description": "投资方列表",
                  "type": "array",
                  "items": {
                    "type": "string"
                  }
                },
                "company": {
                  "description": "融资方公司",
                  "type": "string"
                },
                "funding_amount": {
                  "description": "融资金额",
                  "type": "number"
                },
                "round": {
                  "description": "融资轮次，如A轮、B轮",
                  "type": "string"
                },
                "related_products": {
                  "description": "相关产品",
                  "type": "array",
                  "items": {
                    "type": "string"
                  }
                },
                "publish_date": {
                  "description": "发布日期",
                  "type": "string",
                  "format": "date"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                }
              },
              "required": ["event_type", "investors", "company", "funding_amount", "round", "publish_date", "source"]
            }
            ```
        - `高管变动 (Executive Change)`: `公司`, `变动高管`, `职位`, `变动类型(上任/离职)`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "高管变动事件",
              "description": "描述公司高管职位发生变动的事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘高管变动’",
                  "type": "string",
                  "enum": ["高管变动"]
                },
                "company": {
                  "description": "相关公司",
                  "type": "string"
                },
                "executive_name": {
                  "description": "变动的高管姓名",
                  "type": "string"
                },
                "position": {
                  "description": "相关职位",
                  "type": "string"
                },
                "change_type": {
                  "description": "变动类型，如上任、离职",
                  "type": "string",
                  "enum": ["上任", "离职"]
                },
                "change_date": {
                  "description": "变动日期",
                  "type": "string",
                  "format": "date"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                }
              },
              "required": ["event_type", "company", "executive_name", "position", "change_type", "change_date", "source"]
            }
            ```
        - `法律诉讼 (Legal Proceeding)`: `原告`, `被告`, `诉讼原因`, `涉及金额`, `判决结果`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "法律诉讼事件",
              "description": "描述公司涉及的法律诉讼事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘法律诉讼’",
                  "type": "string",
                  "enum": ["法律诉讼"]
                },
                "plaintiff": {
                  "description": "原告方",
                  "type": "string"
                },
                "defendant": {
                  "description": "被告方",
                  "type": "string"
                },
                "cause_of_action": {
                  "description": "诉讼原因",
                  "type": "string"
                },
                "amount_involved": {
                  "description": "涉及金额",
                  "type": "number"
                },
                "judgment": {
                  "description": "判决结果",
                  "type": "string"
                },
                "filing_date": {
                  "description": "立案日期",
                  "type": "string",
                  "format": "date"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                }
              },
              "required": ["event_type", "plaintiff", "defendant", "cause_of_action", "filing_date", "source"]
            }
            ```
        - `业绩报告 (Financial Report)`: `公司`, `报告期`, `营收`, `净利润`, `同比增长率`
        - `合作合资 (Cooperation & Joint Venture)`: `合作方`, `合作领域`, `合作方式`, `合作目标`, `合作期限`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "合作合资事件",
              "description": "描述公司之间进行合作或成立合资公司的事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘合作合资’",
                  "type": "string",
                  "enum": ["合作合资"]
                },
                "partners": {
                  "description": "合作方列表",
                  "type": "array",
                  "items": {
                    "type": "string"
                  }
                },
                "domain": {
                  "description": "合作领域",
                  "type": "string"
                },
                "method": {
                  "description": "合作方式",
                  "type": "string"
                },
                "goal": {
                  "description": "合作目标",
                  "type": "string"
                },
                "validity_period": {
                  "description": "合作期限",
                  "type": "string"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                },
                "publish_date": {
                  "description": "发布日期",
                  "type": "string",
                  "format": "date"
                }
              },
              "required": ["event_type", "partners", "domain", "publish_date", "source"]
            }
            ```
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "业绩报告事件",
              "description": "描述公司发布业绩报告的事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘业绩报告’",
                  "type": "string",
                  "enum": ["业绩报告"]
                },
                "company": {
                  "description": "发布报告的公司",
                  "type": "string"
                },
                "reporting_period": {
                  "description": "报告期，如2023年Q4",
                  "type": "string"
                },
                "revenue": {
                  "description": "营业收入",
                  "type": "number"
                },
                "net_profit": {
                  "description": "净利润",
                  "type": "number"
                },
                "year_on_year_growth": {
                  "description": "同比增长率",
                  "type": "string"
                },
                "publish_date": {
                  "description": "发布日期",
                  "type": "string",
                  "format": "date"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                }
              },
              "required": ["event_type", "company", "reporting_period", "revenue", "net_profit", "publish_date", "source"]
            }
            ```
    - **集成电路领域**: 由于缺乏统一标准，将根据行业知识（如：供应链、制造流程、市场动态等）自定义事件类型及属性。经过细化，更新后的 Schema 如下：
      - **事件类型**:
        - `产能扩张 (Capacity Expansion)`: `公司`, `工厂地点`, `投资金额`, `新增产能`, `技术节点`, `预计投产时间`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "产能扩张事件",
              "description": "描述公司扩大生产能力的事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘产能扩张’",
                  "type": "string",
                  "enum": ["产能扩张"]
                },
                "company": {
                  "description": "进行产能扩张的公司",
                  "type": "string"
                },
                "location": {
                  "description": "工厂地点",
                  "type": "string"
                },
                "investment_amount": {
                  "description": "投资金额",
                  "type": "number"
                },
                "new_capacity": {
                  "description": "新增产能详情",
                  "type": "string"
                },
                "technology_node": {
                  "description": "技术节点，如28nm",
                  "type": "string"
                },
                "estimated_production_time": {
                  "description": "预计投产时间",
                  "type": "string",
                  "format": "date"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                }
              },
              "required": ["event_type", "company", "location", "new_capacity", "estimated_production_time", "source"]
            }
            ```
        - `技术突破 (Technological Breakthrough)`: `公司/研究机构`, `技术名称`, `关键指标(如制程、良率)`, `应用领域`, `发布日期`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "技术突破事件",
              "description": "描述在技术上取得重要进展的事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘技术突破’",
                  "type": "string",
                  "enum": ["技术突破"]
                },
                "organization": {
                  "description": "取得技术突破的公司或研究机构",
                  "type": "string"
                },
                "technology_name": {
                  "description": "技术名称",
                  "type": "string"
                },
                "key_metrics": {
                  "description": "关键指标，如制程、良率",
                  "type": "string"
                },
                "application_field": {
                  "description": "应用领域",
                  "type": "string"
                },
                "release_date": {
                  "description": "发布日期",
                  "type": "string",
                  "format": "date"
                },
                "source": {
                  "description": "信息来源",
                  "type": "string"
                }
              },
              "required": ["event_type", "organization", "technology_name", "release_date", "source"]
            }
            ```
        - `供应链动态 (Supply Chain Dynamics)`: `公司`, `动态类型(断供/涨价/合作/事故)`, `影响环节`, `涉及物料`, `影响对象(上/下游)`
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "供应链动态事件",
              "description": "描述供应链中发生的动态变化事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘供应链动态’",
                  "type": "string",
                  "enum
        - `合作合资 (Collaboration/Joint Venture)`: 
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "合作合资事件",
              "description": "描述两个或多个实体之间的合作或合资事件",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘合作合资’",
                  "type": "string",
                  "enum": ["合作合资"]
                },
                "trigger_words": {
                  "description": "触发事件的关键动词或短语",
                  "type": "array",
                  "items": {
                    "type": "string"
                  }
                },
                "partners": {
                  "description": "合作或合资的参与方列表",
                  "type": "array",
                  "items": {
                    "type": "string"
                  }
                },
                "domain": {
                  "description": "合作或合资所属的业务领域或行业",
                  "type": "string"
                },
                "method": {
                  "description": "合作的具体方式，如技术授权、共同研发、成立合资公司等",
                  "type": "string"
                },
                "goal": {
                  "description": "合作旨在达成的目标",
                  "type": "string"
                },
                "validity_period": {
                  "description": "合作协议的有效期",
                  "type": "string"
                },
                "source": {
                  "description": "信息来源，如新闻链接或公告名称",
                  "type": "string"
                },
                "publish_date": {
                  "description": "信息发布的日期",
                  "type": "string",
                  "format": "date"
                }
              },
              "required": ["event_type", "partners", "domain", "source", "publish_date"]
            }
            ```
        - `知识产权 (Intellectual Property)`: `公司`, `IP类型(专利诉讼/授权/收购)`, `IP详情`, `涉及金额`, `判决结果`
        - `领域事件 (Domain Event)`:
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "领域事件",
              "description": "描述一个通用的领域事件，作为具体事件类型的基础模板，并增强了对复杂、因果和时空信息的支持。",
              "type": "object",
              "properties": {
                "event_id": {
                  "description": "事件的唯一标识符，可使用UUID",
                  "type": "string"
                },
                "event_type": {
                  "description": "具体的事件类型，如‘产能扩张’、‘技术突破’等",
                  "type": "string"
                },
                "trigger": {
                  "description": "触发事件的关键词或短语",
                  "type": "string"
                },
                "arguments": {
                  "description": "事件的核心参与元素（论元），以键值对形式存储",
                  "type": "object",
                  "additionalProperties": {
                    "type": "string"
                  }
                },
                "sub_events": {
                  "description": "构成复杂事件的子事件列表，每个子事件遵循此schema",
                  "type": "array",
                  "items": {
                    "$ref": "#"
                  }
                },
                "description": {
                  "description": "对事件的自然语言描述",
                  "type": "string"
                },
                "timestamp": {
                  "description": "事件发生的精确时间或日期",
                  "type": "string",
                  "format": "date-time"
                },
                "location": {
                  "description": "事件发生的地理位置",
                  "type": "string"
                },
                "status": {
                  "description": "事件的当前状态",
                  "type": "string",
                  "enum": [
                    "潜在",
                    "已确认",
                    "进行中",
                    "已完成",
                    "已取消"
                  ]
                },
                "confidence_score": {
                  "description": "事件提取或预测的可信度评分，范围0到1",
                  "type": "number",
                  "minimum": 0,
                  "maximum": 1
                },
                "source": {
                  "description": "信息来源，如新闻链接或公告名称",
                  "type": "string"
                },
                "publish_date": {
                  "description": "信息发布的日期",
                  "type": "string",
                  "format": "date"
                }
              },
              "required": [
                "event_id",
                "event_type",
                "arguments",
                "source",
                "publish_date"
              ]
            }
            ```
        - `领域事件关系 (Domain Event Relation)`:
          - **Schema**:
            ```json
            {
              "$schema": "http://json-schema.org/draft-07/schema#",
              "title": "领域事件关系",
              "description": "描述两个或多个领域事件之间的因果、时序或逻辑关系",
              "type": "object",
              "properties": {
                "event_type": {
                  "description": "事件类型，固定为‘领域事件关系’",
                  "type": "string",
                  "enum": ["领域事件关系"]
                },
                "source_event_id": {
                  "description": "源事件的唯一标识符",
                  "type": "string"
                },
                "target_event_id": {
                  "description": "目标事件的唯一标识符",
                  "type": "string"
                },
                "relation_type": {
                  "description": "两个事件之间的关系类型",
                  "type": "string",
                  "enum": ["因果关系", "时序关系", "条件关系", "关联关系"]
                },
                "description": {
                  "description": "对事件关系的文字描述",
                  "type": "string"
                },
                "confidence_score": {
                  "description": "关系的可信度评分，范围0到1",
                  "type": "number",
                  "minimum": 0,
                  "maximum": 1
                },
                "source": {
                  "description": "信息来源，如新闻链接或公告名称",
                  "type": "string"
                },
                "publish_date": {
                  "description": "信息发布的日期",
                  "type": "string",
                  "format": "date"
                }
              },
              "required": ["event_type", "source_event_id", "target_event_id", "relation_type", "source", "publish_date"]
            }
            ```
3.  **事件抽取与图谱构建**: 
    - **数据预处理**: 设计一个统一的模块，负责处理不同来源的语料，如纯文本、PDF、网页等，将其转化为统一的文本格式。
    - **事件抽取 (Prompt-based)**: 
      - 设计针对性的提示词（Prompt），指导大型语言模型（LLM）根据预定义的事件Schema，从预处理后的文本中识别和抽取出事件的关键属性。
      - Prompt模板需要包含清晰的指令、事件定义、属性列表以及输出格式要求（如JSON）。
      - **示例Prompt**: `你是一个金融事件分析专家。请从以下文本中，抽取出“公司并购”事件，并以JSON格式返回结果，包含'收购方', '被收购方', '交易金额', '公告日期'等字段。如果信息不存在，请用null填充。文本：“【公司A宣布以50亿美元收购公司B】......”`
    - **图谱构建 (HyperGraphRAG)**:
      - 将LLM抽取的事件JSON数据，转换为`HyperGraphRAG`接受的`unique_contexts`格式。
      - 每个事件可以被视为一个“超边（Hyperedge）”，连接所有相关的实体（节点），如`公司`、`人物`、`产品`等。
      - 调用`rag.insert(unique_contexts)`方法，将事件超边和相关实体节点批量存入知识超图。

## 三、 工作流程规划

采用测试驱动开发（TDD）的模式，分阶段进行。

1.  **阶段一：调研与设计（已完成）**
    - [x] 研究`HyperGraphRAG`的核心功能。
    - [x] 调研金融和集成电路领域的事件本体/Schema。
    - [x] 完成`architecture.md`的初步设计。

5.  **阶段一附录：外部资源调研结论**

    - **调研节点**: 001
    - **使用工具**: `Sequential Thinking`, `DuckDuckGo Search Server`, `Context7`
    - **策略**:
      1. 分析通用金融事件研究工具 (`eventstudy` 仓库)。
      2. 搜索特定领域（集成电路、银行业务）的金融事件语料库、本体或工具。
    - **结论与洞察**:
      1.  **通用工具的价值与局限**: `eventstudy` 这样的量化分析工具为“金融事件”提供了结构化的定义范式（事件标识、日期、关联实体），这对我们设计图谱的 Schema 很有启发。然而，它本身是事件分析工具，而非事件抽取工具，不提供语料收集功能。 (详见: `docs/related_research.md`)
      2.  **特定领域语料库的稀缺性**: 经过多轮搜索，未发现公开的、专门针对“集成电路”或“银行业务”的、已标注的金融事件语料库。相关的数据集主要集中在硬件设计 (`AICircuit`) 或文字识别 (`ICText`) 等非金融领域。 (详见: `docs/irrelevant_research.md`)
      3.  **策略调整**: 鉴于直接的领域语料库难以获取，项目需要调整策略。下一步的重点将是：
          - **转向通用金融事件语料库 (已尝试)**: 尝试搜索通用事件抽取数据集（如 ACE, MAVEN），但由于工具限制或资源稀缺，未能获取有效信息。**结论：寻找现成语料库的路径已走到尽头。**
          - **探索弱监督/无监督方法 (下一步重点)**: 鉴于上述结论，项目正式将重心转向探索如何利用NLP工具链（如 spaCy, Flair, OpenNRE 等）和弱监督/无监督方法，从大规模无标注新闻文本中自动发现和构建事件语料。需要研究的重点包括：命名实体识别 (NER)、关系抽取 (Relation Extraction) 和事件论元抽取 (Event Argument Extraction) 的实现方案。

    - **待调研的外部资源**:
      - [casually-fine-tuned/awesome-financial-events](https://github.com/casually-fine-tuned/awesome-financial-events)
      - [Event-Study-Tools/event-study](https://github.com/Event-Study-Tools/event-study)
      - [acorn-datasets/sentifm](https://huggingface.co/datasets/acorn-datasets/sentifm)
      - [hi-alice/FNER](https://github.com/hi-alice/FNER)
      - [midas-research/financial-event-dataset](https://github.com/midas-research/financial-event-dataset)
      - [iss-lab/FinancialRiskDetection](https://github.com/iss-lab/FinancialRiskDetection)
      - [ChanceFocus/ma-dataset](https://github.com/ChanceFocus/ma-dataset)
      - [yangna111/FinCorpus](https://github.com/yangna111/FinCorpus)
      - [zheshen-ot/Financial-Disaster-Analysis](https://github.com/zheshen-ot/Financial-Disaster-Analysis)

## 会话存档 (2024-07-29)

**核心结论**:

当前工作暂时告一段落。已将项目的中期目标和技术选型（弱监督方法、spaCy、Flair、OpenNRE等）记录在案，以便后续工作可以无缝衔接。

**下一步行动计划**:

1.  **待续**: 下次将从“技术原型开发 (弱监督)”阶段开始，重点评估和选择合适的NLP工具链，并着手实现初步的事件语料自动构建流水线。


**核心结论**:

经过对多个参考仓库的分析，我们确认了项目的核心技术路径：利用大型语言模型 (LLM) 和 Prompt Engineering 进行金融事件抽取。同时，我们认识到，在缺少大规模标注数据的情况下，直接微调模型存在挑战。因此，项目的下一个关键阶段是探索弱监督和无监督方法，以自动化地从无结构文本中构建事件语料。

**下一步行动计划**:

1.  **事件 Schema 细化**: 基于 `SentiFM` 数据集和金融领域知识，进一步完善 `architecture.md` 中定义的事件 Schema，使其更具通用性和覆盖性。
2.  **技术原型开发 (弱监督)**:
    *   **工具选型**: 重点评估 `spaCy`, `Flair`, `OpenNRE` 等NLP工具在命名实体识别 (NER) 和关系抽取任务上的表现。
    *   **实现路径**: 设计并实现一个初步的流水线，该流水线能够：
        1.  利用预训练的 NER 模型识别文本中的实体（如公司、人名、地点）。
        2.  基于预定义的规则或启发式方法，抽取实体间的潜在关系。
        3.  将抽取的“伪标签”数据用于训练一个初步的事件抽取模型。
3.  **知识图谱集成**: 将抽取的结构化事件数据，按照预定义的图谱模式，存入知识图谱（如 Neo4j），并记录相关决策于本文档。

**决策记录**: 本次会话的所有分析和规划都已记录在案，并同步更新到项目的知识图谱中，以便于未来的任务延续和决策追溯。


2.  **阶段二：原型开发**
    - [ ] **TDD-1**: 开发数据预处理模块，并编写单元测试，确保能正确处理txt, pdf等格式。
    - [ ] **TDD-2**: 开发事件抽取模块，针对每个事件类型编写测试用例，验证Prompt的有效性和LLM抽取的准确性。
    - [ ] **TDD-3**: 开发图谱构建模块，测试事件数据能否成功转换为超图结构并存入`HyperGraphRAG`。

3.  **阶段三：评估与迭代**
    - [ ] 使用标准数据集或人工标注数据，评估端到端的事件抽取和图谱构建效果。
    - [ ] 根据评估结果，迭代优化Prompt设计、事件Schema和处理流程。
    - [ ] 完善文档和代码，确保可复现性和可扩展性。

## 四、 核心技术路径探索 (弱监督/无监督)

- **调研节点**: 002
- **使用工具**: `Sequential Thinking`, `DuckDuckGo Search Server`, `GitHub`
- **策略**:
  1.  **初步探索**: 借助 `DuckDuckGo` 搜索 "financial event extraction dataset"、"sentece embedding financial" 等关键词，寻找公开的数据集和前沿方法。
  2.  **深入分析**: 针对有价值的 GitHub 仓库（如 `SentiFM`），分析其实现方法、数据来源和核心思想。
  3.  **总结归纳**: 整合搜索结果，明确当前技术主流，识别现有工具的优缺点，并为本项目制定清晰的技术选型和实施路径。
- **结论与洞察**:
  1.  **LLM + Prompt 是主流**: 当前，利用大型语言模型（LLM）结合精心设计的提示（Prompt）进行事件抽取，是学术界和工业界的主流方案。此方法在零样本（Zero-shot）和少样本（Few-shot）场景下表现优越，适合本项目当前缺乏大规模标注数据的现状。
  2.  **弱监督/无监督是关键**: 直接获取覆盖目标领域的、高质量的标注数据成本高昂。因此，探索弱监督（Weak Supervision）或无监督（Unsupervised）方法，自动化地从海量无结构文本中构建训练语料，是项目成功的关键。例如，可以利用 `spaCy`、`Flair` 等工具进行命名实体识别（NER），再结合规则或远程监督（Distant Supervision）构建伪标签数据。
  3.  **`SentiFM` 的启示**: `acorn-datasets/sentifm` 数据集及其相关研究，为我们提供了宝贵的参考。它不仅定义了一套清晰的金融事件分类体系，还验证了“句子嵌入（Sentence Embeddings）+ 分类器”的技术路径在金融情绪分析任务上的有效性。这启发我们可以借鉴此思路，将事件抽取任务部分转化为一个分类问题。
- **下一步行动计划**:
  - [ ] **细化事件 Schema**: 参考 `SentiFM` 和其他金融知识，完善 `architecture.md` 中定义的事件类型和属性。
  - [ ] **技术原型开发 (弱监督)**: 启动一个技术原型，重点评估 `spaCy`, `Flair`, `OpenNRE` 等NLP库在实体识别、关系抽取任务上的表现，并搭建一个初步的伪标签数据生成流水线。
  - [ ] **知识图谱集成**: 规划如何将抽取的结构化事件数据，高效地存入 `HyperGraphRAG`，并同步更新本文档。

## 五、 目录结构说明

- `/materials`: 存放项目附加的程序，例如绘图的原始文件、思维导图等。这些文件需要同步到GitHub，但在项目构建或部署时可以忽略。

## 六、 提交规范

- 代码、测试、文档分支提交，Commit 规范：
  ```
  feat: 添加子任务 XXX 实现及单元测试
  fix: 修复子任务 XXX 异常场景
  docs: 更新 architecture.md 中 XXX 节点
  ```