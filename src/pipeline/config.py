"""Configuration: typed defaults + optional TOML override. No business rule lives in the code path."""

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Rules:
    """Row-level business rules used by the validator."""

    statuses: frozenset = frozenset({"CREATED", "PAID", "SHIPPED", "DELIVERED", "CANCELLED", "REFUNDED"})
    currencies: frozenset = frozenset({"USD", "EUR", "GBP", "INR"})
    min_cents: int = 1
    max_cents: int = 100_000_000
    order_id_pattern: str = r"^ORD-\d{6,12}$"
    customer_id_pattern: str = r"^CUST-\d{4,12}$"


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/warehouse.db"
    log_file: str = "logs/pipeline.log"
    chunk_size: int = 5000
    rules: Rules = field(default_factory=Rules)


DEFAULT_RULES = Rules()
DEFAULT_SETTINGS = Settings()
DEFAULT_CONFIG_PATH = Path("config/pipeline.toml")


def _build(cls, data: dict, section: str):
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"unknown key(s) in [{section}]: {sorted(unknown)}")
    return data


def load_settings(path=None) -> Settings:
    """Load settings from `path` (or config/pipeline.toml if present); otherwise defaults."""
    path = Path(path) if path else (DEFAULT_CONFIG_PATH if DEFAULT_CONFIG_PATH.exists() else None)
    if path is None:
        return DEFAULT_SETTINGS
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc

    rules_data = _build(Rules, data.pop("rules", {}), "rules")
    for key in ("statuses", "currencies"):
        if key in rules_data:
            rules_data[key] = frozenset(str(x).upper() for x in rules_data[key])
    top = _build(Settings, data, "root")
    top.pop("rules", None)
    rules = Rules(**{**Rules().__dict__, **rules_data})
    if rules.min_cents < 1 or rules.max_cents < rules.min_cents:
        raise ConfigError("rules: require 1 <= min_cents <= max_cents")
    return Settings(**{**Settings().__dict__, **top, "rules": rules})
