# Power BI Measures (generated)

**Do not hand-edit this file.** It is generated from `warehouse/semantic_layer.py::MEASURE_DOCS` by
`warehouse/generate_powerbi_measures_doc.py`, which is the single source of truth for what each
measure means, in both SQL (used by this prototype's DuckDB backend) and DAX (for Power BI).

For each measure below: paste the DAX into Power BI Desktop's "New Measure" on the appropriate
table (named in the SQL view's underlying table), after importing the tables per
POWERBI_MIGRATION.md.

---

## Mission completion rate by unit

*Source view (this prototype): `v_mission_completion_by_unit`*

**Definition:** Percentage of missions where status is 'Complete' AND the objective was met, out of all missions with a KNOWN outcome for that unit. Missions with an unrecorded objective outcome (mostly Aborted missions with no follow-up entry) are excluded from the denominator rather than counted as failures.

**DAX for Power BI:**

```dax
Mission Completion Rate = 
DIVIDE(
    CALCULATE(COUNTROWS(missions), missions[status] = "Complete", missions[objective_met] = TRUE),
    CALCULATE(COUNTROWS(missions), NOT ISBLANK(missions[objective_met]))
) * 100
```

**Modeling notes:** Group by unit_name (from the units table via the unit_id relationship) in a Power BI matrix/bar visual; no Power Query transform needed beyond the import.

---

## Mission completion rate by mission type

*Source view (this prototype): `v_mission_completion_by_type`*

**Definition:** Same completion-rate definition as by-unit, grouped by mission type instead.

**DAX for Power BI:**

```dax
Same 'Mission Completion Rate' measure as above, grouped by missions[mission_type] instead of unit_name.
```

**Modeling notes:** No separate measure needed -- one DAX measure, two different grouping columns on the visual.

---

## Mission count by month

*Source view (this prototype): `v_mission_count_by_month`*

**Definition:** Count of missions per unit per calendar month, based on the parsed mission date.

**DAX for Power BI:**

```dax
Mission Count = COUNTROWS(missions)
```

**Modeling notes:** Requires a Date table (Power BI can auto-generate one, or import one) related to missions[mission_date_parsed]; group by unit_name and the Date table's month column.

---

## Average mission duration by type

*Source view (this prototype): `v_avg_duration_by_type`*

**Definition:** Average duration_hours per mission type. Missions with a missing or previously-invalid (negative) duration are excluded from the average rather than treated as zero; the count of excluded missions is shown alongside so the average's coverage is visible.

**DAX for Power BI:**

```dax
Avg Mission Duration = AVERAGE(missions[duration_hours])
Missions Missing Duration = CALCULATE(COUNTROWS(missions), ISBLANK(missions[duration_hours]))
```

**Modeling notes:** AVERAGE() already ignores blanks in DAX, matching the SQL view's exclusion behavior -- no extra filter needed for the average itself, only for the companion missing-count measure.

---

## Average equipment readiness by unit

*Source view (this prototype): `v_avg_readiness_by_unit`*

**Definition:** Average readiness_pct across all equipment types for a unit. Records flagged as impossible (>100%) during cleansing are excluded.

**DAX for Power BI:**

```dax
Avg Readiness = AVERAGE(readiness[readiness_pct])
```

**Modeling notes:** The >100% rows are already excluded upstream in pipeline/clean.py before export, so the imported readiness table has no impossible values left to filter in DAX.

---

## Average readiness by equipment type

*Source view (this prototype): `v_avg_readiness_by_equipment`*

**Definition:** Average readiness_pct grouped by equipment type across all units.

**DAX for Power BI:**

```dax
Same 'Avg Readiness' measure as above, grouped by readiness[equipment_type] instead of unit_name.
```

**Modeling notes:** One DAX measure, different grouping column on the visual.

---

## Training/certification currency rate by unit

*Source view (this prototype): `v_training_currency_by_unit`*

**Definition:** Percentage of certification records that are still within their validity window as of today, out of all records where currency could be determined for that unit. Records with a missing or previously-invalid (negative) validity period are excluded entirely rather than counted as expired -- 'unknown' is not the same as 'lapsed.' This measure is the first one built from the training_records source, which arrives as JSON (not CSV) and relates to a unit through personnel rather than directly, unlike every other measure in this registry.

**DAX for Power BI:**

```dax
Training Currency Rate = 
VAR CurrentCount = COUNTROWS(
    FILTER(training_records, EDATE(training_records[completed_on], training_records[valid_months]) >= TODAY())
)
RETURN DIVIDE(CurrentCount, COUNTROWS(training_records)) * 100
```

**Modeling notes:** Group by unit_name reached via the training_records -> personnel -> units relationship chain (two hops, unlike the direct unit_id relationships every other measure here uses) -- Power BI handles multi-hop filtering automatically once both relationships are modeled, no extra DAX needed. EDATE() is Power BI's month-arithmetic equivalent of the SQL view's INTERVAL 1 MONTH computation.

---

## Training/certification currency rate by certification type

*Source view (this prototype): `v_training_currency_by_certification`*

**Definition:** Same currency-rate definition as by-unit, grouped by certification type instead.

**DAX for Power BI:**

```dax
Same 'Training Currency Rate' measure as above, grouped by training_records[certification] instead of unit_name.
```

**Modeling notes:** One DAX measure, different grouping column on the visual.

---

## Average maintenance downtime by equipment type

*Source view (this prototype): `v_maintenance_downtime_by_equipment`*

**Definition:** Average downtime_hours per maintenance/discrepancy event, grouped by equipment type -- the same equipment_type vocabulary readiness uses, so this can be compared side-by-side with readiness by equipment type. Events with a missing or previously-invalid (negative) downtime are excluded from the average rather than treated as zero. This is the first measure in the registry sourced from an actual SQL database (SQLite) rather than a flat file -- see pipeline/clean.py::clean_maintenance_events.

**DAX for Power BI:**

```dax
Avg Maintenance Downtime = AVERAGE(maintenance_events[downtime_hours])
Discrepancy Count = COUNTROWS(maintenance_events)
```

**Modeling notes:** AVERAGE() ignores blanks in DAX, matching the SQL view's exclusion behavior for missing/invalid downtime.

---

## Maintenance discrepancy resolution rate by unit

*Source view (this prototype): `v_maintenance_resolution_rate_by_unit`*

**Definition:** Percentage of maintenance events marked resolved, out of all events where resolution status could be determined for that unit. The source system stores 'resolved' under several inconsistent encodings (1/0, Y/N, true/false) -- normalized to a single boolean during cleansing (pipeline/clean.py) before this measure is computed, so the messiness is resolved once, upstream, not re-handled by every consumer of this view.

**DAX for Power BI:**

```dax
Resolution Rate = 
DIVIDE(
    CALCULATE(COUNTROWS(maintenance_events), maintenance_events[resolved] = TRUE),
    CALCULATE(COUNTROWS(maintenance_events), NOT ISBLANK(maintenance_events[resolved]))
) * 100
```

**Modeling notes:** The multiple 'resolved' text encodings (1/0, Y/N, true/false) need to be normalized to a proper Power BI boolean/Yes-No column in Power Query BEFORE this measure works -- unlike the SQLite source, Parquet export preserves whatever normalization pipeline/clean.py already did, so this should already be a clean boolean on import; verify the column type rather than re-deriving it.

---
