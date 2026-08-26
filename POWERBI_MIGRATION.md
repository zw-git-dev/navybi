# Migrating This Prototype's Dashboards to Power BI

This is the step-by-step path from "this prototype's own dashboards" to "Power BI report," using the same cleaned data and the same measure definitions, decided and scoped in [PLAN.md](PLAN.md).

## Environment constraint — read this first

**Power BI Desktop is Windows-only.** This prototype was built on a Mac, which cannot run Power BI Desktop natively. To actually build the Power BI model described below you'll need one of:
- A Windows machine or VM with Power BI Desktop installed, or
- The Power BI Service (app.powerbi.com) in a browser, which supports importing files and building reports without Desktop, though the modeling experience (relationships, DAX authoring) is more limited than Desktop's.

Nothing in this repo can validate the Power BI side directly from this environment — the export and docs below are prepared so that whoever has Windows/Power BI access can complete the import quickly, not so it can be tested here.

## What gets migrated vs. what stays custom

Per the integration approach decided for this prototype: **Power BI becomes the dashboard/reporting layer; the conversational "Ask a question" layer stays custom** and keeps querying this app's own semantic layer (DuckDB now) directly — it does not go through Power BI. This preserves the explainability/safeguard behavior documented in [QUESTION_TEST_LOG.md](QUESTION_TEST_LOG.md), which would be lost if the NL feature were handed off to Power BI's own Copilot/Q&A.

So: Overview / Trends / Map dashboard pages (`api/routers/dashboard.py` + `frontend/src/pages/`) → candidates to be rebuilt as native Power BI reports. Ask a question, Drill-down, Governance panel → stay in this app regardless of Power BI adoption.

## Step 1 — Export the data

```bash
python3 warehouse/export_for_powerbi.py
```

This writes `units.parquet`, `personnel.parquet`, `missions.parquet`, `readiness.parquet`, `training_records.parquet`, `maintenance_events.parquet`, and a `manifest.json` describing table relationships into `data/powerbi_export/`. Re-run it any time the cleaned data changes and you want Power BI's source files refreshed.

**Why the raw cleaned tables and not the pre-aggregated views:** `v_mission_completion_by_unit` etc. are DuckDB-specific rollups. Importing those into Power BI would mean the "80% vs 100% completion" logic exists as a frozen snapshot, not something Power BI can slice/filter dynamically. Importing the underlying `missions`/`readiness`/`units` tables and defining the same logic as DAX measures (Step 3) keeps Power BI's normal strengths — interactive filtering, drill-through, cross-filtering — intact.

## Step 2 — Import into Power BI Desktop

1. **Get Data → Parquet** (or Folder, pointing at `data/powerbi_export/`) for each of the six files.
2. Confirm data types on load, especially:
   - `missions.mission_date_parsed` → Date
   - `missions.objective_met` → True/False (exported as a proper nullable boolean; Power BI should detect this correctly)
   - `readiness.readiness_pct` → Decimal Number
   - `training_records.completed_on_parsed` → Date
   - `training_records.valid_months` → Whole Number
   - `maintenance_events.event_date_parsed` → Date
   - `maintenance_events.resolved_normalized` → True/False (already normalized to a real boolean during cleansing — see Step 4's note on this measure)

## Step 3 — Rebuild relationships (Model view)

Per `data/powerbi_export/manifest.json`, create these relationships (all many-to-one, single direction, from the fact table to `units`):

| From table | From column | To table | To column |
|---|---|---|---|
| missions | unit_id | units | unit_id |
| readiness | unit_id | units | unit_id |
| personnel | unit_id | units | unit_id |
| training_records | person_id | personnel | person_id |
| maintenance_events | unit_id | units | unit_id |

This gives `units` the role of the dimension table — filtering or slicing by `unit_name` or `community` on any visual will correctly filter missions, readiness, personnel, and maintenance events together. `training_records` is one hop further out: it relates to `units` only *through* `personnel`, since certification records are logged per person, not per unit. Both relationships need to be modeled for a "training currency by unit" visual to filter correctly — Power BI chains multi-hop filtering automatically once each individual relationship exists, no extra DAX required for the chaining itself.

Optional: let Power BI auto-generate a Date table (Modeling → New Table → date hierarchy) and relate it to `missions.mission_date_parsed` (and optionally `training_records.completed_on_parsed`) for month/quarter/year drill-down on the Trends-equivalent visuals.

## Step 4 — Add the DAX measures

See [POWERBI_MEASURES.md](POWERBI_MEASURES.md) — generated directly from this codebase's measure registry (`warehouse/semantic_layer.py::MEASURE_DOCS`), not hand-written, so it can't silently drift from what this app actually computes. Paste each DAX formula into a new measure on the table named in its definition.

If you change a measure's logic, update `MEASURE_DOCS` in `warehouse/semantic_layer.py` (both the SQL-facing description and the `dax` field) and regenerate the doc:

```bash
python3 warehouse/generate_powerbi_measures_doc.py
```

## Step 5 — Rebuild the visuals

Rough equivalence to this prototype's own pages:

| This app's page | Power BI equivalent |
|---|---|
| Overview (KPI tiles + bar charts) | Card visuals for the KPIs, clustered bar charts for completion rate / readiness / training currency / maintenance downtime & resolution rate |
| Trends (line chart by month) | Line chart visual, Date table on the axis, `unit_name` as legend |
| Map | Power BI's built-in Map or ArcGIS Maps visual, `mission_lat`/`mission_lon`, color by `status` |
| Drill-down / verify | Power BI table visual with slicers, or just "See Data" on any visual |

## Step 6 — Keep both in sync going forward

Any time `pipeline/clean.py` or `warehouse/measures.sql`/`MEASURE_DOCS` changes:
1. Re-run `python3 warehouse/export_for_powerbi.py` to refresh the Parquet files.
2. Re-run `python3 warehouse/generate_powerbi_measures_doc.py` if any measure definition changed.
3. In Power BI Desktop, "Refresh" the dataset to pick up the new Parquet files; re-paste any changed DAX measure.

There's no automated sync between the two yet — that's a reasonable next step once there's a real Power BI workspace to publish to (e.g., a scheduled export + a Power BI dataflow), but it's out of scope until Step 1-5 above have actually been exercised once by hand.
