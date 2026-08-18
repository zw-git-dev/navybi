"""
Dashboard data endpoints. Every query here reads ONLY from the DuckDB
semantic layer (warehouse/semantic_layer.py) -- never from data/raw or
data/clean directly -- so what a user sees on a dashboard and what the NL
query layer answers are guaranteed to be computed the same way. The SQL
below is carried over unchanged from the old app/dashboard.py Streamlit
rendering; only the Streamlit calls around it were dropped.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends

from api.deps import get_current_user
from api.utils import df_to_records
from warehouse import semantic_layer as sl

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/overview")
def overview():
    missions = sl.query("SELECT * FROM v_missions")
    completion_by_unit = sl.query("SELECT * FROM v_mission_completion_by_unit ORDER BY completion_rate_pct DESC")
    readiness_by_unit = sl.query("SELECT * FROM v_avg_readiness_by_unit")
    training_by_unit = sl.query("SELECT * FROM v_training_currency_by_unit ORDER BY currency_rate_pct DESC")
    downtime_by_equipment = sl.query("SELECT * FROM v_maintenance_downtime_by_equipment ORDER BY avg_downtime_hours DESC")
    resolution_by_unit = sl.query("SELECT * FROM v_maintenance_resolution_rate_by_unit ORDER BY resolution_rate_pct DESC")

    total_missions = len(missions)
    overall_completion = sl.query("""
        SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Complete' AND objective_met = true)
            / NULLIF(COUNT(*) FILTER (WHERE objective_met IS NOT NULL), 0), 1) AS pct
        FROM v_missions
    """)["pct"][0]
    overall_readiness = sl.query("SELECT ROUND(AVG(readiness_pct), 1) AS pct FROM v_readiness")["pct"][0]
    overall_training_currency = sl.query("""
        SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE is_current) / NULLIF(COUNT(*), 0), 1) AS pct
        FROM v_training_records
    """)["pct"][0]

    return {
        "kpis": {
            "total_missions": total_missions,
            "overall_completion_pct": overall_completion,
            "overall_readiness_pct": overall_readiness,
            "overall_training_currency_pct": overall_training_currency,
        },
        "completion_by_unit": df_to_records(completion_by_unit),
        "readiness_by_unit": df_to_records(readiness_by_unit),
        "training_by_unit": df_to_records(training_by_unit),
        "downtime_by_equipment": df_to_records(downtime_by_equipment),
        "resolution_by_unit": df_to_records(resolution_by_unit),
        "completion_measure_description": sl.MEASURE_DOCS["v_mission_completion_by_unit"]["description"],
    }


@router.get("/trends")
def trends():
    units = sl.query("SELECT DISTINCT unit_name FROM v_missions ORDER BY unit_name")["unit_name"].tolist()
    by_month = sl.query("SELECT * FROM v_mission_count_by_month ORDER BY mission_month")
    by_type = sl.query("SELECT * FROM v_avg_duration_by_type ORDER BY avg_duration_hours DESC")

    return {
        "units": units,
        "mission_count_by_month": df_to_records(by_month),
        "avg_duration_by_type": df_to_records(by_type),
    }


@router.get("/map")
def map_data():
    statuses = sl.query("SELECT DISTINCT status FROM v_missions")["status"].tolist()
    missions = sl.query("SELECT * FROM v_missions")

    return {
        "statuses": statuses,
        "missions": df_to_records(missions),
    }


@router.get("/drilldown")
def drilldown():
    units = sl.query("SELECT DISTINCT unit_name FROM v_missions ORDER BY unit_name")["unit_name"].tolist()
    df = sl.query("SELECT * FROM v_missions ORDER BY mission_date DESC")

    return {
        "units": units,
        "missions": df_to_records(df),
    }
