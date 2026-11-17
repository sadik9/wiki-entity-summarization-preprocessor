from pathlib import Path

from relief.config import Settings


def test_defaults_without_environment():
    settings = Settings.from_env({})
    assert settings.db_host == "localhost" and settings.db_port == 5432
    assert settings.neo4j_uri == "bolt://localhost:7687"
    assert settings.device == "auto"
    assert settings.runs_dir == Path("relief-runs")


def test_reads_the_preprocessor_env_names():
    settings = Settings.from_env({
        "DB_HOST": "wiki-es-pg", "DB_PORT": "15432", "DB_NAME": "wikies", "DB_USER": "u", "DB_PASSWORD": "p",
        "NEO4J_HOST": "wiki-es-neo", "NEO4J_PORT": "17687", "NEO4J_USER": "n", "NEO4J_PASSWORD": "q",
        "RELIEF_DEVICE": "cpu", "RELIEF_RUNS_DIR": "/runs", "RELIEF_GIT_COMMIT": "abc123",
    })
    assert settings.db_port == 15432 and isinstance(settings.db_port, int)
    assert settings.neo4j_uri == "bolt://wiki-es-neo:17687"
    assert (settings.db_password, settings.neo4j_password) == ("p", "q")
    assert settings.device == "cpu"
    assert settings.runs_dir == Path("/runs")
    assert settings.git_commit == "abc123"


def test_empty_values_fall_back_to_defaults():
    assert Settings.from_env({"DB_PORT": "", "RELIEF_DEVICE": ""}) == Settings.from_env({})
