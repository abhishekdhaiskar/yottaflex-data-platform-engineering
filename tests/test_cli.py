"""CLI contract: exit codes are what an orchestrator (cron/Airflow) relies on."""

import pytest

from conftest import HEADER, good
from qpipe.cli import main


@pytest.fixture
def env(tmp_path):
    return ["--db", str(tmp_path / "w.db"), "--log-file", str(tmp_path / "l.log")]


def test_end_to_end_exit_codes(env, tmp_path, write, capsys):
    cust = tmp_path / "c.csv"
    cust.write_text("customer_id,customer_name,country_code\nCUST-000001,A,IN\n")
    assert main(env + ["load-customers", "--file", str(cust)]) == 0
    assert main(env + ["ingest", "--file", str(write([good()]))]) == 0
    bad = write([good()], header=[c if c != "amount" else "total" for c in HEADER])
    assert main(env + ["ingest", "--file", str(bad)]) == 1  # FAILED run => non-zero exit
    assert main(env + ["reconcile", "--out", str(tmp_path / "r.md")]) == 0
    assert (tmp_path / "r.md").read_text().startswith("# Reconciliation report")
    assert main(env + ["runs"]) == 0
    assert "FAILED" in capsys.readouterr().out


def test_bad_config_exits_2(env, tmp_path):
    cfg = tmp_path / "bad.toml"
    cfg.write_text("nonsense = 1\n")
    assert main(env + ["--config", str(cfg), "runs"]) == 2


def test_replay_dry_run_via_cli(env, tmp_path, write):
    assert main(env + ["replay", "--dry-run"]) == 0
