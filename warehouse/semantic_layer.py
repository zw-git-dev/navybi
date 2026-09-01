"""
Semantic layer: loads cleaned tables into DuckDB and applies the measure/view
definitions in measures.sql. This module is the single source of truth for
"what tables exist, how they relate, and what each measure means" -- the
dashboard and the NL query layer both import from here rather than touching
CSVs or writing their own SQL against raw tables.
"""
import os
import threading

import duckdb
import pandas as pd

CLEAN_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "clean")
DB_PATH = os.path.join(os.path.dirname(__file__), "navybi.duckdb")
MEASURES_SQL_PATH = os.path.join(os.path.dirname(__file__), "measures.sql")

# Everything after this marker in measures.sql depends on the multimodal
# extraction tables and is applied only when those tables are present.
MULTIMODAL_SECTION_MARKER = "-- MULTIMODAL LAYER"

# Plain-language documentation for every measure, shown in the governance
# panel and used by the NL layer to explain *why* a number means what it
# claims to mean. Keeping this next to the SQL (measures.sql) is the seed of
# the "transparent, explainable" requirement -- a measure without this entry
# should not be considered demo-ready.
#
# Each entry also carries a "dax" equivalent. This is the Power BI swap point:
# when this prototype's tables get imported into a Power BI dataset (see
# POWERBI_MIGRATION.md), these DAX formulas are the measures to paste in, so
# the same definition is never re-derived by hand in two places and drifting
# apart is a documentation error, not a silent inconsistency. A measure added
# here without a "dax" entry should be treated as not migration-ready.
MEASURE_DOCS = {
    "v_mission_completion_by_unit": {
        "label": "Mission completion rate by unit",
        "description": (
            "Percentage of missions where status is 'Complete' AND the objective "
            "was met, out of all missions with a KNOWN outcome for that unit. "
            "Missions with an unrecorded objective outcome (mostly Aborted "
            "missions with no follow-up entry) are excluded from the denominator "
            "rather than counted as failures."
        ),
        "table": "v_mission_completion_by_unit",
        "dax": (
            "Mission Completion Rate = \n"
            "DIVIDE(\n"
            "    CALCULATE(COUNTROWS(missions), missions[status] = \"Complete\", missions[objective_met] = TRUE),\n"
            "    CALCULATE(COUNTROWS(missions), NOT ISBLANK(missions[objective_met]))\n"
            ") * 100"
        ),
        "power_query_notes": "Group by unit_name (from the units table via the unit_id relationship) in a Power BI matrix/bar visual; no Power Query transform needed beyond the import.",
    },
    "v_mission_completion_by_type": {
        "label": "Mission completion rate by mission type",
        "description": "Same completion-rate definition as by-unit, grouped by mission type instead.",
        "table": "v_mission_completion_by_type",
        "dax": "Same 'Mission Completion Rate' measure as above, grouped by missions[mission_type] instead of unit_name.",
        "power_query_notes": "No separate measure needed -- one DAX measure, two different grouping columns on the visual.",
    },
    "v_mission_count_by_month": {
        "label": "Mission count by month",
        "description": "Count of missions per unit per calendar month, based on the parsed mission date.",
        "table": "v_mission_count_by_month",
        "dax": "Mission Count = COUNTROWS(missions)",
        "power_query_notes": "Requires a Date table (Power BI can auto-generate one, or import one) related to missions[mission_date_parsed]; group by unit_name and the Date table's month column.",
    },
    "v_avg_duration_by_type": {
        "label": "Average mission duration by type",
        "description": (
            "Average duration_hours per mission type. Missions with a missing or "
            "previously-invalid (negative) duration are excluded from the average "
            "rather than treated as zero; the count of excluded missions is shown "
            "alongside so the average's coverage is visible."
        ),
        "table": "v_avg_duration_by_type",
        "dax": (
            "Avg Mission Duration = AVERAGE(missions[duration_hours])\n"
            "Missions Missing Duration = CALCULATE(COUNTROWS(missions), ISBLANK(missions[duration_hours]))"
        ),
        "power_query_notes": "AVERAGE() already ignores blanks in DAX, matching the SQL view's exclusion behavior -- no extra filter needed for the average itself, only for the companion missing-count measure.",
    },
    "v_avg_readiness_by_unit": {
        "label": "Average equipment readiness by unit",
        "description": (
            "Average readiness_pct across all equipment types for a unit. Records "
            "flagged as impossible (>100%) during cleansing are excluded."
        ),
        "table": "v_avg_readiness_by_unit",
        "dax": "Avg Readiness = AVERAGE(readiness[readiness_pct])",
        "power_query_notes": "The >100% rows are already excluded upstream in pipeline/clean.py before export, so the imported readiness table has no impossible values left to filter in DAX.",
    },
    "v_avg_readiness_by_equipment": {
        "label": "Average readiness by equipment type",
        "description": "Average readiness_pct grouped by equipment type across all units.",
        "table": "v_avg_readiness_by_equipment",
        "dax": "Same 'Avg Readiness' measure as above, grouped by readiness[equipment_type] instead of unit_name.",
        "power_query_notes": "One DAX measure, different grouping column on the visual.",
    },
    "v_training_currency_by_unit": {
        "label": "Training/certification currency rate by unit",
        "description": (
            "Percentage of certification records that are still within their validity "
            "window as of today, out of all records where currency could be determined "
            "for that unit. Records with a missing or previously-invalid (negative) "
            "validity period are excluded entirely rather than counted as expired -- "
            "'unknown' is not the same as 'lapsed.' This measure is the first one built "
            "from the training_records source, which arrives as JSON (not CSV) and "
            "relates to a unit through personnel rather than directly, unlike every "
            "other measure in this registry."
        ),
        "table": "v_training_currency_by_unit",
        "dax": (
            "Training Currency Rate = \n"
            "VAR CurrentCount = COUNTROWS(\n"
            "    FILTER(training_records, EDATE(training_records[completed_on], training_records[valid_months]) >= TODAY())\n"
            ")\n"
            "RETURN DIVIDE(CurrentCount, COUNTROWS(training_records)) * 100"
        ),
        "power_query_notes": (
            "Group by unit_name reached via the training_records -> personnel -> units relationship chain "
            "(two hops, unlike the direct unit_id relationships every other measure here uses) -- Power BI "
            "handles multi-hop filtering automatically once both relationships are modeled, no extra DAX needed. "
            "EDATE() is Power BI's month-arithmetic equivalent of the SQL view's INTERVAL 1 MONTH computation."
        ),
    },
    "v_training_currency_by_certification": {
        "label": "Training/certification currency rate by certification type",
        "description": "Same currency-rate definition as by-unit, grouped by certification type instead.",
        "table": "v_training_currency_by_certification",
        "dax": "Same 'Training Currency Rate' measure as above, grouped by training_records[certification] instead of unit_name.",
        "power_query_notes": "One DAX measure, different grouping column on the visual.",
    },
    "v_maintenance_downtime_by_equipment": {
        "label": "Average maintenance downtime by equipment type",
        "description": (
            "Average downtime_hours per maintenance/discrepancy event, grouped by equipment "
            "type -- the same equipment_type vocabulary readiness uses, so this can be "
            "compared side-by-side with readiness by equipment type. Events with a missing "
            "or previously-invalid (negative) downtime are excluded from the average rather "
            "than treated as zero. This is the first measure in the registry sourced from an "
            "actual SQL database (SQLite) rather than a flat file -- see "
            "pipeline/clean.py::clean_maintenance_events."
        ),
        "table": "v_maintenance_downtime_by_equipment",
        "dax": (
            "Avg Maintenance Downtime = AVERAGE(maintenance_events[downtime_hours])\n"
            "Discrepancy Count = COUNTROWS(maintenance_events)"
        ),
        "power_query_notes": "AVERAGE() ignores blanks in DAX, matching the SQL view's exclusion behavior for missing/invalid downtime.",
    },
    "v_maintenance_resolution_rate_by_unit": {
        "label": "Maintenance discrepancy resolution rate by unit",
        "description": (
            "Percentage of maintenance events marked resolved, out of all events where "
            "resolution status could be determined for that unit. The source system stores "
            "'resolved' under several inconsistent encodings (1/0, Y/N, true/false) -- "
            "normalized to a single boolean during cleansing (pipeline/clean.py) before this "
            "measure is computed, so the messiness is resolved once, upstream, not re-handled "
            "by every consumer of this view."
        ),
        "table": "v_maintenance_resolution_rate_by_unit",
        "dax": (
            "Resolution Rate = \n"
            "DIVIDE(\n"
            "    CALCULATE(COUNTROWS(maintenance_events), maintenance_events[resolved] = TRUE),\n"
            "    CALCULATE(COUNTROWS(maintenance_events), NOT ISBLANK(maintenance_events[resolved]))\n"
            ") * 100"
        ),
        "power_query_notes": (
            "The multiple 'resolved' text encodings (1/0, Y/N, true/false) need to be normalized to a proper "
            "Power BI boolean/Yes-No column in Power Query BEFORE this measure works -- unlike the SQLite "
            "source, Parquet export preserves whatever normalization pipeline/clean.py already did, so this "
            "should already be a clean boolean on import; verify the column type rather than re-deriving it."
        ),
    },
    "v_debrief_mentions_by_equipment": {
        "label": "Debrief-reported discrepancy mentions by equipment type",
        "description": (
            "How many post-mission debriefs describe a problem with each equipment "
            "type, broken out by severity. Sourced from UNSTRUCTURED text -- free-text "
            "debrief narratives and transcribed spoken debriefs -- via the extraction "
            "pipeline in ingest/, not from any structured field. Counts what crews "
            "actually reported in prose, which is a different question from what the "
            "maintenance system recorded; see the corroboration measure for the "
            "comparison between the two."
        ),
        "table": "v_debrief_mentions_by_equipment",
        "dax": (
            "Debrief Mentions = CALCULATE(COUNTROWS(debrief_extractions), "
            "debrief_extractions[has_discrepancy] = TRUE)"
        ),
        "power_query_notes": "Group by debrief_extractions[equipment_type]; the column already shares the conformed equipment vocabulary used by readiness and maintenance, so it can sit on the same axis as those measures.",
    },
    "v_debrief_discrepancy_rate_by_unit": {
        "label": "Debrief-reported discrepancy rate by unit",
        "description": (
            "Share of a unit's analyzed debriefs that describe an equipment problem "
            "at all. Denominator is every debrief successfully ingested for that unit "
            "(text or audio), so this is a rate over reports analyzed, not over sorties "
            "flown -- a unit whose debriefs weren't captured will be absent rather than "
            "appear to have a perfect record."
        ),
        "table": "v_debrief_discrepancy_rate_by_unit",
        "dax": (
            "Debrief Discrepancy Rate = \n"
            "DIVIDE(\n"
            "    CALCULATE(COUNTROWS(debrief_extractions), debrief_extractions[has_discrepancy] = TRUE),\n"
            "    COUNTROWS(debrief_extractions)\n"
            ") * 100"
        ),
        "power_query_notes": "Group by unit_name via the debrief_extractions -> units relationship on unit_id.",
    },
    "v_narrative_vs_maintenance_corroboration": {
        "label": "Narrative vs. maintenance-record corroboration by equipment type",
        "description": (
            "Cross-modal comparison: how often each equipment type is implicated in "
            "debrief NARRATIVES (unstructured text and audio) versus how many "
            "maintenance events the structured system of record holds for it. Neither "
            "source can produce this measure alone. A ratio well above 1 means crews "
            "are describing problems that comparatively few maintenance write-ups "
            "capture, which points at a reporting-pipeline gap rather than an "
            "equipment fact. Reported as counts plus a ratio and deliberately not as "
            "an alert -- the system's role is to surface the divergence between two "
            "independent sources; a human decides whether it reflects underreporting, "
            "different thresholds for what merits a write-up, or nothing at all."
        ),
        "table": "v_narrative_vs_maintenance_corroboration",
        "dax": (
            "Narrative To Record Ratio = \n"
            "DIVIDE(\n"
            "    CALCULATE(COUNTROWS(debrief_extractions), debrief_extractions[has_discrepancy] = TRUE),\n"
            "    COUNTROWS(maintenance_events)\n"
            ")"
        ),
        "power_query_notes": (
            "Requires both debrief_extractions and maintenance_events related to a shared "
            "equipment_type dimension table. Build that dimension explicitly in Power BI "
            "rather than relating the two fact tables directly -- a conformed dimension is "
            "what makes the two counts comparable on one axis, and it's the same conformed "
            "vocabulary the SQL view relies on."
        ),
    },
    "v_extraction_provenance": {
        "label": "Extraction provenance by modality and extractor",
        "description": (
            "Operational transparency rather than mission analytics: how many facts in "
            "the warehouse came from each source modality (typed text, transcribed "
            "audio) and which extractor produced them (LLM or deterministic rules), "
            "plus mean transcription confidence where applicable. This is the "
            "provenance question an assessor asks first -- where did these numbers come "
            "from, and what produced them."
        ),
        "table": "v_extraction_provenance",
        "dax": "Extraction Count = COUNTROWS(debrief_extractions)",
        "power_query_notes": "Group by debrief_extractions[source_modality] and [extracted_by].",
    },
}


def build_warehouse():
    """(Re)builds the DuckDB warehouse from the cleaned CSVs and applies views."""
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE OR REPLACE TABLE units AS SELECT * FROM read_csv_auto(?)", [os.path.join(CLEAN_DIR, "units.csv")])
    con.execute("CREATE OR REPLACE TABLE personnel AS SELECT * FROM read_csv_auto(?)", [os.path.join(CLEAN_DIR, "personnel.csv")])
    con.execute("CREATE OR REPLACE TABLE missions AS SELECT * FROM read_csv_auto(?)", [os.path.join(CLEAN_DIR, "missions.csv")])
    con.execute("CREATE OR REPLACE TABLE readiness AS SELECT * FROM read_csv_auto(?)", [os.path.join(CLEAN_DIR, "readiness.csv")])
    con.execute("CREATE OR REPLACE TABLE training_records AS SELECT * FROM read_csv_auto(?)", [os.path.join(CLEAN_DIR, "training_records.csv")])
    con.execute("CREATE OR REPLACE TABLE maintenance_events AS SELECT * FROM read_csv_auto(?)", [os.path.join(CLEAN_DIR, "maintenance_events.csv")])

    # Multimodal extractions (ingest/run_ingest.py). Optional on purpose: the
    # unstructured sources need extra dependencies (OCR, speech-to-text) that
    # the core BI application doesn't require, so the warehouse builds fine
    # without them and the multimodal views are simply absent. Creating empty
    # tables instead would be worse -- a view returning zero rows looks like
    # "no discrepancies were reported" rather than "this modality wasn't
    # ingested," and that's exactly the kind of silent wrong answer the rest
    # of this codebase works to avoid.
    for table, filename in [
        ("debrief_extractions", "debrief_extractions.csv"),
        ("form_extractions", "form_extractions.csv"),
    ]:
        path = os.path.join(CLEAN_DIR, filename)
        if os.path.exists(path):
            con.execute(
                f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto(?)", [path]
            )

    with open(MEASURES_SQL_PATH) as f:
        views_sql = f.read()

    # The multimodal views depend on tables that only exist once
    # ingest/run_ingest.py has run. Split there and skip that section
    # entirely when its inputs are absent, rather than letting CREATE VIEW
    # fail mid-build and leave a half-applied warehouse.
    core_sql, _, multimodal_sql = views_sql.partition(MULTIMODAL_SECTION_MARKER)
    has_multimodal = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'debrief_extractions'"
    ).fetchone()[0] > 0

    statements = core_sql
    if has_multimodal:
        statements += multimodal_sql

    for statement in statements.split(";"):
        statement = statement.strip()
        if statement:
            con.execute(statement)

    con.close()


_connection = None
_connection_lock = threading.Lock()


def get_connection():
    """
    Returns a single, process-wide DuckDB connection instead of opening a
    fresh one per call. The API serves every dashboard/query request from
    the same process, and opening/closing a file-backed connection on every
    request (several times per page load) was pure overhead with no
    benefit -- nothing here needs read-your-own-writes isolation across
    connections. Guarded by a lock since FastAPI runs sync route handlers
    in a threadpool, and a single DuckDB connection is not safe for
    concurrent use from multiple threads without one.

    Opened read_only=True deliberately: query() only ever runs SELECTs (the
    only writer is build_warehouse(), which uses its own short-lived
    connection and only runs once, before this persistent connection is
    ever created). DuckDB allows multiple separate processes to hold
    read-only connections to the same file concurrently, but not a
    read-write connection alongside anything else -- opening this one
    read-write would hold an exclusive lock on the file for the entire
    life of the API process, blocking any other process (a one-off script,
    the test suite) from reading the same warehouse file while the API is
    running, which is a real regression this avoids.
    """
    global _connection
    if _connection is None:
        with _connection_lock:
            if _connection is None:
                if not os.path.exists(DB_PATH):
                    build_warehouse()
                _connection = duckdb.connect(DB_PATH, read_only=True)
    return _connection


def query(sql, params=None):
    con = get_connection()
    with _connection_lock:
        if params:
            return con.execute(sql, params).df()
        return con.execute(sql).df()


def cleansing_log_df():
    import json
    log_path = os.path.join(CLEAN_DIR, "cleansing_log.json")
    with open(log_path) as f:
        entries = json.load(f)
    return pd.DataFrame(entries)


if __name__ == "__main__":
    build_warehouse()
    print("Warehouse built at", DB_PATH)
    con = get_connection()
    print(con.execute("SELECT * FROM v_mission_completion_by_unit").df())
    con.close()
