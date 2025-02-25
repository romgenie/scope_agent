"""
Configuration settings for the Scope Agent application.
"""

import os
from typing import Dict, Any

# Default settings
DEFAULT_CONFIG = {
    "projects_dir": "projects",
    "model": "gpt-4o",
    "max_suggestions": 5,
    "auto_save": True
}

class Config:
    """Manages application configuration settings."""
    
    def __init__(self, config_path: str = None):
        """Initialize configuration with default values and optional file loading."""
        self.settings: Dict[str, Any] = DEFAULT_CONFIG.copy()
        
        # Load from file if provided
        if config_path and os.path.exists(config_path):
            self.load_from_file(config_path)
        
        # Override with environment variables
        self.load_from_env()
    
    def load_from_file(self, config_path: str) -> None:
        """Load configuration from a file."""
        try:
            import json
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                self.settings.update(file_config)
        except Exception as e:
            print(f"Error loading configuration from {config_path}: {e}")
    
    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_prefix = "SCOPE_AGENT_"
        
        for key in self.settings.keys():
            env_key = f"{env_prefix}{key.upper()}"
            if env_key in os.environ:
                # Convert types appropriately
                if isinstance(self.settings[key], bool):
                    self.settings[key] = os.environ[env_key].lower() in ('true', 'yes', '1')
                elif isinstance(self.settings[key], int):
                    try:
                        self.settings[key] = int(os.environ[env_key])
                    except ValueError:
                        pass
                else:
                    self.settings[key] = os.environ[env_key]
    
    def get(self, key: str, default=None) -> Any:
        """Get a configuration value with an optional default."""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.settings[key] = value
    
    def save(self, config_path: str) -> bool:
        """Save current configuration to a file."""
        try:
            import json
            with open(config_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving configuration to {config_path}: {e}")
            return False