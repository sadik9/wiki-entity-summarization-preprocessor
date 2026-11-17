import os

import pytest

from relief import checks
from relief.checks import CheckResult, run_checks
from relief.cli import main
from relief.config import Settings


def test_a_failing_check_is_reported_not_raised(monkeypatch):
    def broken(settings):
        raise ConnectionError("refused")

    monkeypatch.setattr(checks, "CHECKS", {"ok": lambda s: CheckResult("ok", True), "broken": broken})
    results = run_checks(Settings())
    assert [(r.name, r.ok) for r in results] == [("ok", True), ("broken", False)]
    assert "ConnectionError: refused" in results[1].details["error"]


def test_exit_code_reflects_failures(monkeypatch, capsys):
    monkeypatch.setattr(checks, "CHECKS", {"broken": lambda s: CheckResult("broken", False)})
    assert main(["check"]) == 1
    monkeypatch.setattr(checks, "CHECKS", {"fine": lambda s: CheckResult("fine", True)})
    assert main(["check", "--json"]) == 0
    assert '"ok": true' in capsys.readouterr().out


integration = pytest.mark.skipif(os.environ.get("RELIEF_INTEGRATION") != "1",
                                 reason="set RELIEF_INTEGRATION=1 to run against the databases")


@pytest.mark.integration
@integration
def test_databases_hold_the_restored_2023_data():
    settings = Settings.from_env()
    postgres = checks.check_postgres(settings)
    neo4j = checks.check_neo4j(settings)
    assert postgres.ok, postgres.details
    assert neo4j.ok, neo4j.details
    # exact counts of the authors' Neo4j-1.0.0 release (2023-05-01 dumps)
    assert neo4j.details["wiki_entities"] == 56_473_512
    assert neo4j.details["has_type"] == 303_735_353
    assert neo4j.details["summary"] == 13_087_324
