"""
Unit tests for the DataProcessor module.
"""
import unittest
import os
from src.data_processor import DataProcessor, process_text, process_pdf

class TestDataProcessor(unittest.TestCase):
    """Test suite for data processing functions."""

    def setUp(self):
        """Set up test files."""
        self.test_dir = 'test_data'
        os.makedirs(self.test_dir, exist_ok=True)
        self.txt_file_path = os.path.join(self.test_dir, 'test.txt')
        with open(self.txt_file_path, 'w', encoding='utf-8') as f:
            f.write('This is a test text file.')

    def tearDown(self):
        """Clean up test files."""
        os.remove(self.txt_file_path)
        os.rmdir(self.test_dir)

    def test_process_text(self):
        """Test reading text from a .txt file."""
        content = process_text(self.txt_file_path)
        self.assertEqual(content, 'This is a test text file.')

    def test_process_pdf(self):
        """Test processing a .pdf file (placeholder)."""
        # This is a placeholder test. 
        # PDF processing requires a real PDF file and a library like PyPDF2.
        content = process_pdf('dummy.pdf')
        self.assertEqual(content, 'This is text extracted from a PDF.')

    def test_data_processor_class(self):
        """Test the DataProcessor class dispatcher."""
        processor = DataProcessor(self.txt_file_path)
        content = processor.process()
        self.assertEqual(content, 'This is a test text file.')

        with self.assertRaises(ValueError):
            unsupported_processor = DataProcessor('test.unsupported')
            unsupported_processor.process()

if __name__ == '__main__':
    unittest.main()