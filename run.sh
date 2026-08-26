#!/usr/bin/env bash
# One-command local run: sets up what's missing, then launches the app.
# Usage:
#   ./run.sh          # development: API on :8000 + Vite dev server on :5173
#   ./run.sh --prod   # production-style: build the SPA, serve everything from :8000
#   ./run.sh --reset  # regenerate synthetic data, warehouse, and users from scratch
#
# Flags combine, e.g. ./run.sh --reset --prod
set -euo pipefail
cd "$(dirname "$0")"

RESET=false
PROD=false
for arg in "$@"; do
    case "$arg" in
        --reset) RESET=true ;;
        --prod) PROD=true ;;
        *) echo "Unknown option: $arg"; echo "Usage: ./run.sh [--reset] [--prod]"; exit 1 ;;
    esac
done

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

if [[ "$PROD" == true ]]; then
    # Production-style: one process, one port, no CORS. api/main.py serves
    # frontend/dist when it exists, so building the SPA is what switches the
    # app into this mode -- and --reload is off, since reloading a served
    # bundle has nothing to watch.
    echo "Building frontend..."
    (cd frontend && npm run build)

    if [[ -z "${JWT_SECRET:-}" ]]; then
        echo "Note: JWT_SECRET is not set — a random signing secret will be generated,"
        echo "  so sessions won't survive a restart. Set it in .env for stable sessions."
    fi

    echo "Starting app (http://localhost:8000)..."
    exec uvicorn api.main:app --host 0.0.0.0 --port 8000
fi

# Development: Vite serves the SPA with hot reload and proxies /api to uvicorn.
# frontend/dist is deliberately not built here, which is what keeps
# api/main.py's static-serving branch inactive.
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
