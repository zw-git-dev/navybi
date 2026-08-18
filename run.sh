#!/usr/bin/env bash
# One-command local run: sets up what's missing, then launches the app.
# Usage:
#   ./run.sh          # normal run (skips steps already done)
#   ./run.sh --reset  # regenerate synthetic data, warehouse, and users from scratch
set -euo pipefail
cd "$(dirname "$0")"

RESET=false
if [[ "${1:-}" == "--reset" ]]; then
    RESET=true
fi

if [[ "$RESET" == true ]]; then
    echo "Resetting: removing generated data, warehouse, and seeded users..."
    rm -rf data/raw warehouse/navybi.duckdb auth/users.json
fi

if [[ ! -d venv ]]; then
    echo "Creating virtualenv..."
    python3 -m venv venv
fi
source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

if [[ ! -d data/raw ]] || [[ -z "$(ls -A data/raw 2>/dev/null)" ]]; then
    echo "Generating synthetic data..."
    python3 data/generate_synthetic_data.py
    echo "Cleaning/ingesting data..."
    python3 pipeline/clean.py
fi

if [[ ! -f warehouse/navybi.duckdb ]]; then
    echo "Building semantic layer..."
    python3 warehouse/semantic_layer.py
fi

if [[ ! -f auth/users.json ]]; then
    echo "Seeding demo users..."
    python3 auth/seed_users.py
fi

if [[ ! -f .env ]]; then
    echo "Note: no .env found — conversational layer will use the keyword-matcher fallback only."
    echo "  Add OPENROUTER_API_KEY and OPENROUTER_MODEL to a .env file to use the real LLM."
fi

if [[ ! -d frontend/node_modules ]]; then
    echo "Installing frontend dependencies..."
    (cd frontend && npm install)
fi

cleanup() {
    echo "Stopping..."
    kill "${API_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting API (http://localhost:8000)..."
uvicorn api.main:app --reload --port 8000 &
API_PID=$!

echo "Starting frontend (http://localhost:5173)..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

wait "$API_PID" "$FRONTEND_PID"
