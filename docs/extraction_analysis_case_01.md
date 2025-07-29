# Extraction Example: Multiple Related Events from a Single Text
# Date: 2025-07-29

## Input Text:
财联社3月29日讯，3月29日，中国移动上海国际海缆登陆局启用仪式暨中国移动上海国际数据中心二期工程启动仪式在上海临港举行，NCP海缆（新跨太平洋海缆系统）首条专线正式开通交付。优刻得（UCloud）在本次启动仪式上宣布，与中国移动上海国际海缆登陆局达成合作意向，作为唯一一家被邀请的试用企业，体验首条NCP海缆专线的畅通与迅捷。

## LLM Output (zai-org/GLM-4.5):
```json
[
  {
    "event_type": "Other",
    "micro_event_type": "FacilityOpening",
    "event_date": null,
    "description": "中国移动上海国际海缆登陆局启用仪式于3月29日在上海临港举行。",
    "involved_entities": [
      {
        "entity_name": "中国移动",
        "entity_type": "Company",
        "role_in_event": "主体"
      }
    ],
    "quantitative_data": null,
    "forecast": null
  },
  {
    "event_type": "Other",
    "micro_event_type": "ProjectLaunch",
    "event_date": null,
    "description": "中国移动上海数据中心二期工程启动仪��于3月29日在上海临港举行。",
    "involved_entities": [
      {
        "entity_name": "中国移动",
        "entity_type": "Company",
        "role_in_event": "主体"
      }
    ],
    "quantitative_data": null,
    "forecast": null
  },
  {
    "event_type": "SupplyChainDisruption",
    "micro_event_type": "CapacityChange",
    "event_date": null,
    "description": "NCP海缆（新跨太平洋海缆系统）首条专线于3月29日正式开通交付。",
    "involved_entities": [
      {
        "entity_name": "中国移动",
        "entity_type": "Company",
        "role_in_event": "运营商"
      },
      {
        "entity_name": "NCP海缆系统",
        "entity_type": "Other",
        "role_in_event": "通信系统"
      }
    ],
    "quantitative_data": null,
    "forecast": null
  },
  {
    "event_type": "Partnership",
    "micro_event_type": "CooperationAgreement",
    "event_date": null,
    "description": "优刻得（UCloud）于3月29日宣布与中国移动上海国际海缆登陆局达成合作意向。",
    "involved_entities": [
      {
        "entity_name": "优刻得",
        "entity_type": "Company",
        "role_in_event": "宣布方"
      },
      {
        "entity_name": "中国移动",
        "entity_type": "Company",
        "role_in_event": "合作方"
      }
    ],
    "quantitative_data": null,
    "forecast": null
  }
]
```
