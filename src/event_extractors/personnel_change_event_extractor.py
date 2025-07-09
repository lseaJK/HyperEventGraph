from typing import Dict, List, Any

class PersonnelChangeEventExtractor:
    def __init__(self):
        self.trigger_words = ["辞职", "离任", "选举", "任命", "聘任"]

    def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中抽取人事变动事件。

        :param text: 输入的文本
        :return: 抽取的事件列表
        """
        events = []
        for word in self.trigger_words:
            if word in text:
                event = {
                    "event_type": "人事变动",
                    "person": "", # 待抽取
                    "company": "", # 待抽取
                    "position": "", # 待抽取
                    "change_type": word,
                    "reason": "",
                    "effective_date": ""
                }
                events.append(event)
                break
        return events