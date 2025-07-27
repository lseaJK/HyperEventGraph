# src/config/config_loader.py
"""
This module provides a centralized function for loading the project's configuration
from a YAML file.
"""

import yaml
from pathlib import Path
from typing import Dict, Any

def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Loads the configuration from a specified YAML file.

    Args:
        config_path: The path to the config.yaml file.

    Returns:
        A dictionary containing the configuration.
        
    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If there is an error parsing the file.
    """
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    try:
        with config_path.open('r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if config is None:
            return {}
        return config
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{config_path}': {e}")
        raise

# Example of a global config object that can be imported by other modules
# This ensures the config is loaded only once.
# Note: The path to the config file needs to be determined reliably.
# For now, we assume it's in the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

# Load the default configuration once when the module is first imported.
# try:
#     CONFIG = load_config(DEFAULT_CONFIG_PATH)
# except FileNotFoundError:
#     print(f"Warning: Default config file not found at {DEFAULT_CONFIG_PATH}. Using empty config.")
#     CONFIG = {}
