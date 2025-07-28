# src/core/config_loader.py
"""
This module provides a centralized function for loading and accessing the 
system-wide configuration from a YAML file. It ensures that configuration
is loaded only once and is accessible globally.
"""

import yaml
from pathlib import Path
from typing import Any, Dict

# Global variable to hold the configuration dictionary
_config: Dict[str, Any] = {}
_config_path: Path | None = None

def load_config(config_path: str | Path):
    """
    Loads the YAML configuration file from the given path and stores it globally.
    This function should be called once at the start of any main workflow script.

    Args:
        config_path: The path to the config.yaml file.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the config file is not valid YAML.
    """
    global _config, _config_path
    
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found at: {path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            _config = yaml.safe_load(f)
        _config_path = path
        print(f"Configuration loaded successfully from '{path}'.")
    except yaml.YAMLError as e:
        print(f"Error parsing YAML configuration file: {e}")
        raise

def get_config() -> Dict[str, Any]:
    """
    Returns the globally loaded configuration dictionary.

    Returns:
        The configuration dictionary.

    Raises:
        ValueError: If the configuration has not been loaded yet.
    """
    if not _config:
        raise ValueError(
            "Configuration has not been loaded. "
            "Please call load_config(path) at the beginning of your script."
        )
    return _config

def get_config_path() -> Path:
    """
    Returns the path of the loaded configuration file.

    Returns:
        The Path object for the config file.
    
    Raises:
        ValueError: If the configuration has not been loaded yet.
    """
    if not _config_path:
        raise ValueError("Configuration has not been loaded.")
    return _config_path


if __name__ == '__main__':
    # Example usage and simple test
    print("Running a simple test of the ConfigLoader...")
    
    # Create a dummy config file
    dummy_config_content = {
        'database': {'path': 'data/master.db'},
        'learning_workflow': {
            'cluster_distance_threshold': 1.5,
            'min_samples_for_schema': 5
        }
    }
    dummy_path = Path("temp_config.yaml")
    with open(dummy_path, 'w', encoding='utf-8') as f:
        yaml.dump(dummy_config_content, f)

    # 1. Test loading
    try:
        load_config(dummy_path)
    except (FileNotFoundError, yaml.YAMLError) as e:
        assert False, f"Test failed during config loading: {e}"

    # 2. Test getting the config
    retrieved_config = get_config()
    print("\nRetrieved config:")
    print(retrieved_config)
    assert retrieved_config['database']['path'] == 'data/master.db'
    
    # 3. Test getting the config path
    retrieved_path = get_config_path()
    print(f"\nRetrieved config path: {retrieved_path}")
    assert retrieved_path == dummy_path

    # 4. Test error on getting before loading
    _config = {} # Reset for testing
    try:
        get_config()
        assert False, "get_config() should have raised ValueError but didn't."
    except ValueError as e:
        print(f"\nSuccessfully caught expected error: {e}")

    # 5. Clean up
    dummy_path.unlink()
    print("\nConfigLoader test complete and temp file removed.")
