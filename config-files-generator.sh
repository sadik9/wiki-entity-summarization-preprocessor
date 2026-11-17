#! /usr/bin/env bash
# Generates .env (read by docker compose AND by the host-side Python scripts) and configs/neo4j.env.
# Existing keys are never overwritten, so you can edit the files and re-run safely.
# Defaults target a 16 GB laptop running Docker Desktop with WSL2; data lives under $WIKIES_HOME (default ~/wikies).

WIKIES_HOME="${WIKIES_HOME:-$HOME/wikies}"

volumes() {
  echo "
########## Volumes (absolute host paths, keep them on the WSL ext4 filesystem) ##########
POSTGRES_VOLUME_PATH=$WIKIES_HOME/pg-data
NEO4J_VOLUME_PATH=$WIKIES_HOME/neo4j-data
WIKIDATA_DUMPS_PATH=$WIKIES_HOME/dumps/wikidata
WIKIPEDIA_DUMPS_PATH=$WIKIES_HOME/dumps/wikipedia
RELIEF_RUNS_PATH=$WIKIES_HOME/relief-runs
RELIEF_MODELS_PATH=$WIKIES_HOME/models
"
}

auths() {
  echo "
########## Auth ##########
DB_NAME=wikies
DB_USER=wikies
DB_PASSWORD=password
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
"
}

hosts() {
  echo "
########## Hosts (as seen from the host; containers get their own values in compose.yaml) ##########
DB_HOST=localhost
NEO4J_HOST=localhost
"
}

apps() {
  echo "
########## Application ##########
WDGB_POOL_SIZE=2
WDGB_HEAP=2g
WPPE_POOL_SIZE=2
WPPE_HEAP=2g
MAX_DB_CONNECTION_POOL=10
SUMMARY_WORKERS=4
# RELIEF: auto (CUDA if available), cuda or cpu
RELIEF_DEVICE=auto
"
}

ports() {
  echo "
########## Ports ##########
DB_PORT=5432
"
}

neo4j_env() {
  echo "# Neo4j
########################################################################
NEO4J_PLUGINS=[\"graph-data-science\",\"apoc\"]
NEO4J_dbms_security_procedures_unrestricted=gds.*,apoc.*
NEO4J_server_config_strict__validation_enabled=false
########## Memory configurations (16 GB laptop) ##########
NEO4J_server_memory_heap_initial__size=3g
NEO4J_server_memory_heap_max__size=3g
NEO4J_server_memory_pagecache_size=3g
NEO4J_dbms_memory_transaction_total_max=1g
########## Keep transaction logs from eating the disk ##########
NEO4J_db_tx__log_rotation_retention__policy=1G size
"
}

initialize_env() {
  echo "*************************************"
  local env_file=$1
  local template_function=$2
  if [ ! -f "$env_file" ]; then
    echo "Creating $env_file..."
    mkdir -p "$(dirname "$env_file")"
    touch "$env_file"
  fi
  echo "[appending '$template_function()' to '$env_file']"
  while IFS= read -r line; do
    if ! grep -q "^${line%%=*}" "$env_file"; then
      echo "$line" >>"$env_file"
    fi
  done < <($template_function)
}

echo "Creating config files..."

initialize_env ".env" volumes
initialize_env ".env" auths
initialize_env ".env" ports
initialize_env ".env" hosts
initialize_env ".env" apps
initialize_env "./configs/neo4j.env" neo4j_env

mkdir -p "$WIKIES_HOME/pg-data" "$WIKIES_HOME/neo4j-data" "$WIKIES_HOME/dumps/wikidata" \
  "$WIKIES_HOME/dumps/wikipedia" "$WIKIES_HOME/dumps/sql" \
  "$WIKIES_HOME/relief-runs" "$WIKIES_HOME/models"

echo "*************************************"
echo "Done."
