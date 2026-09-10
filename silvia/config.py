"""Platform paths and non-secret local configuration."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

from silvia.core import DomainError


def data_home() -> Path:
    if os.environ.get("SILVIA_HOME"):
        return Path(os.environ["SILVIA_HOME"]).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "SilvIA/data"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "silvia"


def config_home() -> Path:
    if os.environ.get("SILVIA_HOME"):
        return data_home() / "config"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "SilvIA"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "silvia"


def load_config(project: Path | None = None) -> dict:
    result: dict = {"providers": {}, "runtime": {"max_parallel": 3}}
    paths = [config_home() / "config.toml"]
    if project:
        paths.append(project / ".silvia/config.toml")
    for path in paths:
        if path.is_file():
            try:
                value = tomllib.loads(path.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError) as exc:
                raise DomainError("configuration", f"Cannot load configuration: {path.name}") from exc
            for section, content in value.items():
                if section not in {"providers", "runtime"} or not isinstance(content, dict):
                    raise DomainError("configuration", f"Unknown configuration section: {section}")
                result.setdefault(section, {}).update(content)
    return result
