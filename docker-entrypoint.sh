#!/usr/bin/env bash
# Generates the synthetic dataset, builds the DuckDB warehouse, and seeds the
# demo accounts on first start, then hands off to the CMD (uvicorn).
#
# Done at start rather than at build time on purpose: it keeps generated data
# out of the image layers, and it means a mounted volume survives restarts
# (the checks below skip regeneration when the artifacts are already there).
set -euo pipefail

if [[ ! -f data/raw/missions.csv ]]; then
    echo "[entrypoint] Generating synthetic data..."
    python data/generate_synthetic_data.py
    echo "[entrypoint] Cleansing and ingesting..."
    python pipeline/clean.py
fi

if [[ ! -f warehouse/navybi.duckdb ]]; then
    echo "[entrypoint] Building semantic layer..."
    python warehouse/semantic_layer.py
fi

if [[ ! -f auth/users.json ]]; then
    echo "[entrypoint] Seeding demo accounts..."
    python auth/seed_users.py
fi

if [[ -z "${JWT_SECRET:-}" ]]; then
    echo "[entrypoint] NOTE: JWT_SECRET is not set. A random signing secret will be"
    echo "[entrypoint]       generated, so sessions won't survive a container restart."
fi

echo "[entrypoint] Starting: $*"
exec "$@"
