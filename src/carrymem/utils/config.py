import json
import logging
import os
from typing import Any, Dict, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

_logger = logging.getLogger("carrymem")

from carrymem.constants import CONFIG_FILE

_DEFAULT_CONFIG_PATH = str(CONFIG_FILE)


class ConfigManager:
    """Load and query configuration from JSON/YAML with env overrides."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.environ.get("CARRYMEM_CONFIG_PATH", _DEFAULT_CONFIG_PATH)
        self.config = self.load_config()

    def get(self, key: str, default: object = None) -> object:
        """Get a configuration value by key.

        Args:
            key: The configuration key, using dot notation (e.g., "storage.data_path").
            default: The default value to return if the key is not found.

        Returns:
            The configuration value or the default.
        """
        env_key = key.upper().replace(".", "_")
        if f"CARRYMEM_{env_key}" in os.environ:
            return os.environ[f"CARRYMEM_{env_key}"]

        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def load_config(self) -> Dict[str, Any]:
        """Load and parse the configuration file, returning an empty dict on error."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                if self.config_path.endswith(".json"):
                    return json.load(f) or {}
                if YAML_AVAILABLE:
                    return yaml.safe_load(f) or {}
                return json.load(f) or {}
        except FileNotFoundError:
            _logger.debug("Config file not found: %s", self.config_path)
            return {}
        except (json.JSONDecodeError, ValueError) as e:
            _logger.warning("Config file parse error: %s: %s", self.config_path, e)
            return {}
        except PermissionError as e:
            _logger.warning("Config file permission denied: %s: %s", self.config_path, e)
            return {}
        # NOTE: Broad exception for config loading is intentional to handle
        # unexpected file system errors, encoding issues, or corrupted config files.
        # All errors are logged and gracefully degraded to empty config.
        except (OSError, ValueError, TypeError) as e:
            _logger.warning("Config file load error: %s: %s", self.config_path, e)
            return {}

    def reload(self):
        """Reload the configuration from file."""
        self.config = self.load_config()

    def get_rules(self, rules_path: Optional[str] = None) -> Dict[str, Any]:
        """Load rule definitions from a JSON/YAML file path."""
        rules_path = rules_path or self.get(
            "rules.config_path", "./config/advanced_rules.json"
        )  # type: ignore[assignment]
        assert rules_path is not None
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                if rules_path.endswith(".json"):
                    return json.load(f) or {}
                if YAML_AVAILABLE and (rules_path.endswith(".yaml") or rules_path.endswith(".yml")):
                    return yaml.safe_load(f) or {}
                if YAML_AVAILABLE:
                    return yaml.safe_load(f) or {}
                return json.load(f) or {}
        except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError, ValueError):
            _logger.debug("Rules file not found: %s", rules_path)
            return {}

    def set(self, key: str, value: object) -> None:
        """Set a configuration value by key.

        Args:
            key: The configuration key, using dot notation (e.g., "storage.data_path").
            value: The value to set.
        """
        keys = key.split(".")
        config = self.config

        # Navigate to the parent level
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value
