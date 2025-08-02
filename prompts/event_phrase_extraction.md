
You are an expert in information extraction. Your task is to read the given text and extract a single, concise "event phrase" that captures the core event.

**Instructions:**

1.  **Identify the Core Event:** Find the main action in the text. What happened? Who did it? To what?
2.  **Be Concise:** The phrase should be short and to the point.
3.  **Use Active Voice:** Phrase it as "Actor + Action + Object" (e.g., "Company X announced product Y," "Regulator Z fined company W").
4.  **Extract, Don't Summarize:** The phrase should be composed of words directly from the text as much as possible.
5.  **Output ONLY the event phrase as a single string.** Do not add any explanation, preamble, or JSON formatting.

**Text:**
```
{text}
```

**Example 1:**
**Text:** "据报道，全球领先的半导体公司台积电于7月20日公布了其第二季度财务报告，显示净利润达到1818亿元新台币，超出了市场预期。"
**Output:**
台积电公布第二季度财务报告

**Example 2:**
**Text:** "在今日的发布会上，华为消费者业务CEO余承东正式推出了全新的Mate 60 Pro手机，该手机搭载了自主研发的麒麟9000S芯片。"
**Output:**
华为推出Mate 60 Pro手机

**Example 3:**
**Text:** "美国商务部昨日宣布，将七家中国超级计算实体列入其所谓的“实体清单”，限制其获取美国技术。"
**Output:**
美国商务部限制中国超级计算实体获取美国技术
