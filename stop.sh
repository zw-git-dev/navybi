#!/usr/bin/env bash
# Stops any running NavyBI dev servers (the FastAPI backend on :8000 and the
# Vite frontend on :5173), including ones started outside of run.sh (e.g.
# manually or left over from a previous session).
set -uo pipefail

PORTS=(8000 5173)
killed_any=false

for port in "${PORTS[@]}"; do
    pids=$(lsof -ti:"$port" 2>/dev/null)
    if [[ -n "$pids" ]]; then
        echo "Stopping process(es) on port $port: $pids"
        kill $pids 2>/dev/null
        killed_any=true
    fi
done

if [[ "$killed_any" == true ]]; then
    sleep 1
    for port in "${PORTS[@]}"; do
        pids=$(lsof -ti:"$port" 2>/dev/null)
        if [[ -n "$pids" ]]; then
            echo "Force-stopping stubborn process(es) on port $port: $pids"
            kill -9 $pids 2>/dev/null
        fi
    done
    echo "Done."
else
    echo "No dev servers found running on ports ${PORTS[*]}."
fi
