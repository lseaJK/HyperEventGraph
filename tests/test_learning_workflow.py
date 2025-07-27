import unittest
from unittest.mock import patch
import io
import sys
from pathlib import Path

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from run_learning_workflow import update_schema_registry_file

class TestLearningWorkflow(unittest.TestCase):

    def setUp(self):
        """Prepare a sample new schema for testing."""
        self.schema_name = "product_launch"
        self.schema_def = {
            "description": "A new product is officially released to the market.",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "The company launching the product."
                },
                "product_name": {
                    "type": "string",
                    "description": "The name of the new product."
                },
                "launch_date": {
                    "type": "string",
                    "description": "The official date of the launch."
                }
            }
        }

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_update_schema_registry_file_output(self, mock_stdout):
        """
        Test that the placeholder function for updating the schema file
        prints the correct code snippets for manual addition.
        """
        # --- Act ---
        update_schema_registry_file(self.schema_name, self.schema_def)

        # --- Assert ---
        # Get the output that was printed to stdout
        output = mock_stdout.getvalue()

        # 1. Check for the main instruction header
        self.assertIn("--- ACTION REQUIRED: Manual Schema Update ---", output)

        # 2. Check for the generated Pydantic class name
        self.assertIn("class ProductLaunch(BaseEvent):", output)
        
        # 3. Check for the class docstring
        self.assertIn('"""A new product is officially released to the market."""', output)

        # 4. Check for the generated fields
        self.assertIn('company: Optional[str] = Field(None, description="The company launching the product.")', output)
        self.assertIn('product_name: Optional[str] = Field(None, description="The name of the new product.")', output)
        
        # 5. Check for the registry update instruction
        self.assertIn("Add the new entry to the EVENT_SCHEMA_REGISTRY dictionary:", output)
        
        # 6. Check for the correct registry entry
        self.assertIn('"product_launch": ProductLaunch,', output)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)