import unittest
from src.event_extractors.personnel_change_event_extractor import PersonnelChangeEventExtractor

class TestPersonnelChangeEventExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = PersonnelChangeEventExtractor()

    def test_extract_resign_event(self):
        text = "公司董事张三因个人原因辞职。"
        events = self.extractor.extract(text)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_type'], '人事变动')
        self.assertEqual(events[0]['change_type'], '辞职')

    def test_extract_appoint_event(self):
        text = "公司任命李四为新任首席技术官。"
        events = self.extractor.extract(text)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_type'], '人事变动')
        self.assertEqual(events[0]['change_type'], '任命')

    def test_no_event(self):
        text = "今天天气真好。"
        events = self.extractor.extract(text)
        self.assertEqual(len(events), 0)

if __name__ == '__main__':
    unittest.main()