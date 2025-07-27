
import unittest
import yaml
from pathlib import Path
import sys

# Add project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.config_loader import load_config

class TestConfigLoader(unittest.TestCase):

    def setUp(self):
        """Set up a temporary config file for testing."""
        self.test_dir = Path("test_config_temp")
        self.test_dir.mkdir(exist_ok=True)
        self.config_file = self.test_dir / "config.yaml"

        self.config_data = {
            "paths": {
                "data_input": "data/raw",
                "database": "db/master_state.db",
                "output": "output"
            },
            "processing": {
                "batch_size": 100,
                "triage_model": "moonshotai/Kimi-K2-Instruct"
            },
            "logging": {
                "level": "INFO"
            }
        }

        with self.config_file.open("w", encoding="utf-8") as f:
            yaml.dump(self.config_data, f)

    def tearDown(self):
        """Clean up the temporary directory and file."""
        self.config_file.unlink()
        self.test_dir.rmdir()

    def test_load_config_success(self):
        """
        Test that the configuration is loaded correctly from a valid YAML file.
        """
        # --- Act ---
        loaded_config = load_config(self.config_file)

        # --- Assert ---
        # 1. Check that the loaded config is not None
        self.assertIsNotNone(loaded_config)

        # 2. Check that the loaded data matches the original data
        self.assertEqual(loaded_config, self.config_data)

        # 3. Check specific nested values
        self.assertEqual(loaded_config['paths']['database'], "db/master_state.db")
        self.assertEqual(loaded_config['processing']['batch_size'], 100)

    def test_load_config_file_not_found(self):
        """
        Test that the function handles a non-existent config file gracefully.
        """
        # --- Act & Assert ---
        non_existent_file = self.test_dir / "non_existent.yaml"
        with self.assertRaises(FileNotFoundError):
            load_config(non_existent_file)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
