"""
Data-quality/governance endpoints -- ported from the old
app/governance_panel.py's data logic (cleansing log, row-count comparison,
measure glossary). Admin-only, same as the Streamlit page was.
"""
import json
import os
import sqlite3
import sys
from functools import lru_cache

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from fastapi import APIRouter, Depends

from api.deps import require_admin
from warehouse import semantic_layer as sl

router = APIRouter(prefix="/api/governance", tags=["governance"], dependencies=[Depends(require_admin)])

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
CLEAN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "clean")


@router.get("/cleansing-log")
@lru_cache(maxsize=1)
def cleansing_log():
    return sl.cleansing_log_df().to_dict(orient="records")


@router.get("/row-counts")
@lru_cache(maxsize=1)
def row_counts():
    # Cached: raw/clean files on disk don't change while the server is
    # running (a real reload requires re-running the pipeline and
    # restarting the process anyway), so re-reading 6 files from disk on
    # every governance-page visit was pure overhead.
    csv_tables = ["units", "personnel", "missions", "readiness"]
    rows = []
    for t in csv_tables:
        raw_count = len(pd.read_csv(os.path.join(RAW_DIR, f"{t}.csv")))
        clean_count = len(pd.read_csv(os.path.join(CLEAN_DIR, f"{t}.csv")))
        rows.append({
            "table": t, "source_format": "CSV", "raw_row_count": raw_count, "clean_row_count": clean_count,
            "rows_removed_or_flagged": raw_count - clean_count if raw_count >= clean_count else 0,
        })

    with open(os.path.join(RAW_DIR, "training_records.json")) as f:
        training_raw_count = len(json.load(f))
    training_clean_count = len(pd.read_csv(os.path.join(CLEAN_DIR, "training_records.csv")))
    rows.append({
        "table": "training_records", "source_format": "JSON", "raw_row_count": training_raw_count,
        "clean_row_count": training_clean_count,
        "rows_removed_or_flagged": training_raw_count - training_clean_count if training_raw_count >= training_clean_count else 0,
    })

    con = sqlite3.connect(os.path.join(RAW_DIR, "maintenance.db"))
    maintenance_raw_count = con.execute("SELECT COUNT(*) FROM maintenance_events").fetchone()[0]
    con.close()
    maintenance_clean_count = len(pd.read_csv(os.path.join(CLEAN_DIR, "maintenance_events.csv")))
    rows.append({
        "table": "maintenance_events", "source_format": "SQLite", "raw_row_count": maintenance_raw_count,
        "clean_row_count": maintenance_clean_count,
        "rows_removed_or_flagged": maintenance_raw_count - maintenance_clean_count if maintenance_raw_count >= maintenance_clean_count else 0,
    })
    return rows


@router.get("/measures")
def measures():
    return [
        {
            "id": name,
            "label": doc["label"],
            "description": doc["description"],
            "table": doc["table"],
            "dax": doc.get("dax", ""),
            "power_query_notes": doc.get("power_query_notes", ""),
        }
        for name, doc in sl.MEASURE_DOCS.items()
    ]
