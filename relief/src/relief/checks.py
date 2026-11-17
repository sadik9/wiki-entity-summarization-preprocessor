"""Environment checks run by `relief check`: GPUs, Postgres and Neo4j, as seen from wherever RELIEF runs."""
from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import Callable

import relief
from relief.config import Settings
from relief.db import neo4j_driver, pg_connect

# Tables of the restored PostgreSQL-1.0.0 database that RELIEF reads
EXPECTED_TABLES = ("wiki_page_to_wiki_data_mappings", "subjects", "wikipedia_pages", "predicates")


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: dict = field(default_factory=dict)


def check_runtime(settings: Settings) -> CheckResult:
    import torch

    details = {
        "relief": relief.__version__,
        "git_commit": settings.git_commit,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda_build": torch.version.cuda,
        "device_setting": settings.device,
        "gpus": [],
    }
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            x = torch.ones(1024, 1024, device=f"cuda:{index}")
            ok = float((x @ x)[0, 0]) == 1024.0         # a real computation on each GPU
            details["gpus"].append({"index": index, "name": torch.cuda.get_device_name(index), "matmul_ok": ok})
    # every visible GPU must compute correctly; no GPU at all is only a failure when the device is forced to "cuda"
    ok = all(g["matmul_ok"] for g in details["gpus"]) and (bool(details["gpus"]) or settings.device != "cuda")
    if settings.device in ("auto", "cuda") and not details["gpus"]:
        details["note"] = "no GPU visible; RELIEF would run on the CPU"
    return CheckResult("runtime", ok, details)


def check_postgres(settings: Settings) -> CheckResult:
    with pg_connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SHOW server_version")
        version = cursor.fetchone()[0]
        cursor.execute("SHOW server_encoding")
        encoding = cursor.fetchone()[0]
        cursor.execute(
            "SELECT c.relname, c.reltuples::bigint FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname = ANY(%s)", (list(EXPECTED_TABLES),)
        )
        estimates = dict(cursor.fetchall())
    missing = [t for t in EXPECTED_TABLES if t not in estimates]
    details = {"server": version, "encoding": encoding, "rows_estimated": estimates, "missing_tables": missing}
    return CheckResult("postgres", not missing and encoding == "UTF8", details)


def check_neo4j(settings: Settings) -> CheckResult:
    with neo4j_driver(settings) as driver, driver.session(database="neo4j") as session:
        version = session.run("CALL dbms.components() YIELD versions RETURN versions[0] AS v").single()["v"]
        # label and relationship-type counts come from the count store, so these are instant
        nodes = session.run("MATCH (n:WikiEntity) RETURN count(n) AS c").single()["c"]
        has_type = session.run("MATCH ()-[r:HAS_TYPE]->() RETURN count(r) AS c").single()["c"]
        summary = session.run("MATCH ()-[r:SUMMARY]->() RETURN count(r) AS c").single()["c"]
        index_online = session.run(
            "SHOW INDEXES YIELD labelsOrTypes, properties, state "
            "WHERE labelsOrTypes = ['WikiEntity'] AND properties = ['entityName'] RETURN state"
        ).single()
    details = {"server": version, "wiki_entities": nodes, "has_type": has_type, "summary": summary,
               "entity_name_index": index_online["state"] if index_online else "missing"}
    return CheckResult("neo4j", nodes > 0 and details["entity_name_index"] == "ONLINE", details)


CHECKS: dict[str, Callable[[Settings], CheckResult]] = {
    "runtime": check_runtime,
    "postgres": check_postgres,
    "neo4j": check_neo4j,
}


def run_checks(settings: Settings, names=None) -> list[CheckResult]:
    results = []
    for name in names or CHECKS:
        try:
            results.append(CHECKS[name](settings))
        except Exception as error:          # report every check, even when one of them cannot connect
            results.append(CheckResult(name, False, {"error": f"{type(error).__name__}: {error}"}))
    return results
