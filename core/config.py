"""
Persistent session configuration manager.
Saves/loads app state to JSON in %LOCALAPPDATA%/ZeeCut/config.json
"""

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger("zee_cut.config")

CONFIG_DIR_NAME = "ZeeCut"
CONFIG_FILE_NAME = "config.json"


@dataclass
class AppConfig:
    """Serializable application configuration."""

    theme: str = "AMOLED Black"
    interface_name: str = ""
    interface_ip: str = ""
    custom_protected_ips: list[str] = field(default_factory=list)
    device_lag_percents: dict[str, int] = field(default_factory=dict)
    last_window_width: int = 1180
    last_window_height: int = 780
    auto_scan_enabled: bool = False
    auto_scan_interval_minutes: int = 3
    new_device_notification_enabled: bool = True


class ConfigManager:
    """Manages loading/saving app configuration to disk."""

    def __init__(self):
        self._lock = threading.Lock()
        self.config = AppConfig()
        self._config_path = self._resolve_config_path()
        self._loaded = False

    @staticmethod
    def _resolve_config_path() -> Path:
        appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        config_dir = appdata / CONFIG_DIR_NAME
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / CONFIG_FILE_NAME

    def load(self) -> AppConfig:
        with self._lock:
            if not self._config_path.exists():
                self._loaded = True
                logger.info("No config file found, using defaults")
                return self.config

            try:
                data = json.loads(self._config_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    logger.warning("Invalid config format, using defaults")
                    return self.config

                valid_keys = {f.name for f in AppConfig.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in valid_keys}

                self.config = AppConfig(**filtered)
                self._loaded = True
                logger.info("Config loaded from %s", self._config_path)
            except Exception as e:
                logger.warning("Failed to load config: %s", e)

            return self.config

    def save(self):
        with self._lock:
            try:
                data = asdict(self.config)
                self._config_path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                logger.info("Config saved to %s", self._config_path)
            except Exception as e:
                logger.warning("Failed to save config: %s", e)

    def update(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
