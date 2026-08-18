"""
Exports the cleaned tables (NOT the pre-aggregated DuckDB views) to Parquet
for Power BI import.

Deliberately exports the raw fact/dimension tables rather than the
v_mission_completion_by_unit-style rollup views: Power BI's own modeling
strengths (relationships + DAX measures) are exactly the fact/dimension
pattern, and importing pre-aggregated views instead would mean the
completion-rate / readiness logic gets re-derived from scratch in Power BI
with no guarantee it matches. Importing the same clean tables this app's
own semantic layer uses, plus the DAX formulas documented in
warehouse/semantic_layer.py::MEASURE_DOCS, keeps both systems computing the
same numbers from the same source of truth.

Run manually (not part of the Streamlit app) whenever the cleaned tables
change and you want to refresh what Power BI would import:
    python3 warehouse/export_for_powerbi.py
"""
import json
import os

import pandas as pd

CLEAN_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "clean")
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "powerbi_export")
os.makedirs(EXPORT_DIR, exist_ok=True)

TABLES = ["units", "personnel", "missions", "readiness", "training_records", "maintenance_events"]

# Describes the star-schema relationships Power BI's model view needs to be
# told about manually after import -- Parquet/CSV carry no relationship
# metadata, so this has to be rebuilt by hand in Power BI Desktop once per
# dataset (see POWERBI_MIGRATION.md for the click-by-click steps).
RELATIONSHIPS = [
    {"from_table": "missions", "from_column": "unit_id", "to_table": "units", "to_column": "unit_id", "cardinality": "many-to-one"},
    {"from_table": "readiness", "from_column": "unit_id", "to_table": "units", "to_column": "unit_id", "cardinality": "many-to-one"},
    {"from_table": "personnel", "from_column": "unit_id", "to_table": "units", "to_column": "unit_id", "cardinality": "many-to-one"},
    # training_records reaches units through personnel (two hops) rather than
    # directly -- the only source in this export with an indirect relationship
    # to the units dimension. Power BI needs both relationships modeled for
    # cross-filtering (unit -> personnel -> training_records) to work.
    {"from_table": "training_records", "from_column": "person_id", "to_table": "personnel", "to_column": "person_id", "cardinality": "many-to-one"},
    {"from_table": "maintenance_events", "from_column": "unit_id", "to_table": "units", "to_column": "unit_id", "cardinality": "many-to-one"},
]

# Columns Power BI should treat as dates so it offers a Date hierarchy/table.
DATE_COLUMNS = {
    "missions": ["mission_date_parsed"],
    "training_records": ["completed_on_parsed"],
    "maintenance_events": ["event_date_parsed"],
}


def main():
    manifest = {"tables": [], "relationships": RELATIONSHIPS}

    for table in TABLES:
        csv_path = os.path.join(CLEAN_DIR, f"{table}.csv")
        df = pd.read_csv(csv_path)

        for col in DATE_COLUMNS.get(table, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # objective_met loads from CSV as an object column mixing True/False/NaN,
        # which Parquet would otherwise store ambiguously. Cast to pandas'
        # nullable boolean dtype so Power BI reads it as a proper tri-state
        # (True/False/blank) boolean column instead of text.
        if table == "missions" and "objective_met" in df.columns:
            df["objective_met"] = df["objective_met"].map({"True": True, "False": False, True: True, False: False}).astype("boolean")
        # resolved_normalized has the same True/False/NaN-as-object issue as
        # objective_met above -- already normalized to a real boolean by
        # pipeline/clean.py, but round-tripped through CSV text in between.
        if table == "maintenance_events" and "resolved_normalized" in df.columns:
            df["resolved_normalized"] = df["resolved_normalized"].map({"True": True, "False": False, True: True, False: False}).astype("boolean")

        parquet_path = os.path.join(EXPORT_DIR, f"{table}.parquet")
        df.to_parquet(parquet_path, index=False)

        manifest["tables"].append({
            "table": table,
            "file": f"{table}.parquet",
            "row_count": len(df),
            "columns": list(df.columns),
        })
        print(f"Exported {table}: {len(df)} rows -> {parquet_path}")

    manifest_path = os.path.join(EXPORT_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest written to {manifest_path}")
    print("See POWERBI_MIGRATION.md for how to import these into Power BI Desktop and rebuild the model.")


if __name__ == "__main__":
    main()
