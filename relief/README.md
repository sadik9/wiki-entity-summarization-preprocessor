# RELIEF

RElation extraction via LexIcal-matching and Entailment-based Filtering: a new ground-truth annotation pipeline for WikES. It decides which of an entity's existing Wikidata edges its Wikipedia lead section and infobox express, and it never invents triples.

- Plan and decisions: `RELIEF-plan.md` (thesis folder)
- What counts as ground truth: [`docs/ground-truth-policy.md`](docs/ground-truth-policy.md)
- Gold-set labelling: [`docs/annotation-guidelines.md`](docs/annotation-guidelines.md)

## Running it (Docker)
RELIEF runs as the `relief` service of this repository's `compose.yaml`, next to Postgres and Neo4j, with GPU access.

```bash
# once: data folders and settings (adds RELIEF_RUNS_PATH, RELIEF_MODELS_PATH, RELIEF_DEVICE to an existing .env)
bash config-files-generator.sh

# build the image; records the git commit in it
bash relief/docker-build.sh

# verify GPUs, Postgres and Neo4j from inside the container
docker compose run --rm relief check

# tests (unit tests always; database tests with RELIEF_INTEGRATION=1)
docker compose run --rm --entrypoint pytest relief -q
docker compose run --rm -e RELIEF_INTEGRATION=1 --entrypoint pytest relief -q
```

- `relief-runs` and `models` folders are mounted from the host, so results and model downloads survive container restarts.
- Per-machine settings (`RELIEF_DEVICE`, paths) live in `.env`.
- On Docker Desktop (Windows + WSL2), run `docker compose` from the WSL distribution that holds the data, not from Windows.

## Running it without Docker (development)
```bash
pip install -r relief/requirements.lock
pip install --no-deps -e relief
relief check          # reads the repository's .env; DB_HOST/NEO4J_HOST=localhost
```

## Layout
| Path | Contents |
|---|---|
| `src/relief/config.py` | settings from environment variables (same names as the preprocessor's `.env`) |
| `src/relief/db.py` | Postgres (UTF-8) and Neo4j connections |
| `src/relief/checks.py`, `cli.py` | `relief check` and the command line |
| `tests/` | unit tests, plus integration tests against the restored 2023 databases |
| `requirements.lock` | exact versions of the working environment on `sol` (CUDA 12.6 PyTorch) |
| `Dockerfile`, `docker-build.sh` | the image |
