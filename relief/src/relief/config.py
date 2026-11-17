"""Settings, read from environment variables.

The variable names are the ones the preprocessor's `.env` already uses (see config-files-generator.sh), so the
same `.env` serves the databases, the old annotator and RELIEF. Inside Docker, compose.yaml overrides the hosts
with the container names.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "wikies"
    db_user: str = "wikies"
    db_password: str = ""
    neo4j_host: str = "localhost"
    neo4j_port: int = 7687
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    # "auto" uses CUDA when available, otherwise the CPU
    device: str = "auto"
    runs_dir: Path = Path("relief-runs")
    git_commit: str = "unknown"

    @property
    def neo4j_uri(self) -> str:
        return f"bolt://{self.neo4j_host}:{self.neo4j_port}"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        def get(name: str, default):
            value = env.get(name)
            return default if value in (None, "") else type(default)(value)

        return cls(
            db_host=get("DB_HOST", cls.db_host),
            db_port=get("DB_PORT", cls.db_port),
            db_name=get("DB_NAME", cls.db_name),
            db_user=get("DB_USER", cls.db_user),
            db_password=get("DB_PASSWORD", cls.db_password),
            neo4j_host=get("NEO4J_HOST", cls.neo4j_host),
            neo4j_port=get("NEO4J_PORT", cls.neo4j_port),
            neo4j_user=get("NEO4J_USER", cls.neo4j_user),
            neo4j_password=get("NEO4J_PASSWORD", cls.neo4j_password),
            device=get("RELIEF_DEVICE", cls.device),
            runs_dir=Path(get("RELIEF_RUNS_DIR", str(cls.runs_dir))),
            git_commit=get("RELIEF_GIT_COMMIT", cls.git_commit),
        )
