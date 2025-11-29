import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from .logger import get_logger

logger = get_logger("AronaSettings")

class AronaSettings:
    DEFAULT_SETTINGS = {
        "host": "127.0.0.1",
        "port": 47500,
        "max_connections": 10,
        "log_level": "INFO",
    }

    def __init__(self, config_path: Optional[Path] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path.home() / ".aronanet" / "config.yaml"

        
        self.settings: Dict[str, Any] = self.DEFAULT_SETTINGS.copy()
        self._ensure_config_dir()
        self.load()

    def _ensure_config_dir(self):
        """Create config directory if missing"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

        except Exception as e:
            logger.error(f"Failed to create config directory: {e} :(")

    def load(self):
        """Load settings from YAML, or create default if missing"""
        if not self.config_path.exists():
            self.save()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                self.settings.update(loaded)

        except yaml.YAMLError as e:
            logger.error(f"YAML error while loading config: {e} :/")

        except Exception as e:
            logger.error(f"Failed to load config: {e} :(")

    def save(self):
        """Save current settings to YAML"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self.settings, f, default_flow_style=False, sort_keys=False)

        except Exception as e:
            logger.error(f"Failed to save config: {e} :(")

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value: Any, save: bool = True):
        self.settings[key] = value
        if save:
            self.save()

    def reset(self):
        """Reset all settings to default"""
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.save()
        logger.info("Settings reset to default :|")