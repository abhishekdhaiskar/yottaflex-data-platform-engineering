import pytest

from conftest import HEADER, good
from qpipe import ingest
from qpipe.config import DEFAULT_SETTINGS, ConfigError, Rules, load_settings
from qpipe.validation import validate_record


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_settings() == DEFAULT_SETTINGS


def test_shipped_config_matches_code_defaults():
    """config/pipeline.toml documents the defaults - they must never drift apart."""
    assert load_settings("config/pipeline.toml") == DEFAULT_SETTINGS


def test_rules_are_configurable_not_hardcoded(tmp_path, conn, write):
    cfg = tmp_path / "c.toml"
    cfg.write_text('chunk_size = 10\n[rules]\ncurrencies = ["JPY"]\nstatuses = ["PAID"]\nmax_cents = 5000\n')
    s = load_settings(cfg)
    assert s.chunk_size == 10 and s.rules.currencies == frozenset({"JPY"})
    ok, errs = validate_record(
        dict(zip(HEADER, good(cur="JPY", status="PAID", amount="50.00"), strict=False)), {"CUST-000001"}, s.rules
    )
    assert errs == [] and ok.currency == "JPY"
    _, errs = validate_record(dict(zip(HEADER, good(amount="50.01"), strict=False)), {"CUST-000001"}, s.rules)
    assert {c for c, _ in errs} >= {"INVALID_VALUE", "INVALID_ENUM"}
    # and the whole pipeline honours it
    r = ingest.ingest_file(conn, write([good(cur="USD")]), rules=s.rules)
    assert r.rows_quarantined == 1


def test_unknown_key_is_rejected(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text("[rules]\ncurrencyes = []\n")
    with pytest.raises(ConfigError):
        load_settings(cfg)


def test_invalid_bounds_rejected(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text("[rules]\nmin_cents = 10\nmax_cents = 5\n")
    with pytest.raises(ConfigError):
        load_settings(cfg)


def test_rules_object_is_immutable():
    with pytest.raises(AttributeError):
        Rules().min_cents = 5
