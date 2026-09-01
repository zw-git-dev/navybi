-- Semantic layer views.
-- These are the ONLY objects the dashboard and the NL query layer are allowed
-- to read from -- nothing downstream ever queries data/clean/*.csv directly.
-- That single choke point is what makes "explainable and verifiable" possible:
-- there is exactly one place where relationships and business logic are defined.

CREATE OR REPLACE VIEW v_missions AS
SELECT
    m.mission_id,
    m.unit_id,
    u.unit_name,
    u.community,
    u.home_base,
    u.lat AS unit_lat,
    u.lon AS unit_lon,
    m.mission_type,
    m.mission_date_parsed AS mission_date,
    m.status,
    m.objective_met,
    m.duration_hours,
    m.lat AS mission_lat,
    m.lon AS mission_lon
FROM missions m
JOIN units u ON m.unit_id = u.unit_id
WHERE m.is_valid_unit = true
  AND m.mission_date_parsed IS NOT NULL;

CREATE OR REPLACE VIEW v_readiness AS
SELECT
    r.record_id,
    r.unit_id,
    u.unit_name,
    u.community,
    r.equipment_type,
    r.month_index,
    r.readiness_pct
FROM readiness r
JOIN units u ON r.unit_id = u.unit_id
WHERE r.data_quality_flag IS NULL;

-- Measure: mission completion rate = share of missions with status Complete
-- AND objective_met = true, out of all missions with a known objective outcome
-- (missions with a null objective_met, e.g. most Aborted missions, are
-- excluded from the denominator rather than counted as failures, since
-- "unknown" and "failed" are not the same thing).
CREATE OR REPLACE VIEW v_mission_completion_by_unit AS
SELECT
    unit_id,
    unit_name,
    community,
    COUNT(*) FILTER (WHERE objective_met IS NOT NULL) AS missions_with_known_outcome,
    COUNT(*) FILTER (WHERE status = 'Complete' AND objective_met = true) AS missions_objective_met,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'Complete' AND objective_met = true)
        / NULLIF(COUNT(*) FILTER (WHERE objective_met IS NOT NULL), 0), 1
    ) AS completion_rate_pct
FROM v_missions
GROUP BY unit_id, unit_name, community;

CREATE OR REPLACE VIEW v_mission_completion_by_type AS
SELECT
    mission_type,
    COUNT(*) FILTER (WHERE objective_met IS NOT NULL) AS missions_with_known_outcome,
    COUNT(*) FILTER (WHERE status = 'Complete' AND objective_met = true) AS missions_objective_met,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'Complete' AND objective_met = true)
        / NULLIF(COUNT(*) FILTER (WHERE objective_met IS NOT NULL), 0), 1
    ) AS completion_rate_pct
FROM v_missions
GROUP BY mission_type;

CREATE OR REPLACE VIEW v_mission_count_by_month AS
SELECT
    unit_id,
    unit_name,
    date_trunc('month', mission_date) AS mission_month,
    COUNT(*) AS mission_count
FROM v_missions
GROUP BY unit_id, unit_name, date_trunc('month', mission_date);

CREATE OR REPLACE VIEW v_avg_duration_by_type AS
SELECT
    mission_type,
    ROUND(AVG(duration_hours), 2) AS avg_duration_hours,
    COUNT(*) FILTER (WHERE duration_hours IS NULL) AS missions_missing_duration
FROM v_missions
GROUP BY mission_type;

CREATE OR REPLACE VIEW v_avg_readiness_by_unit AS
SELECT
    unit_id,
    unit_name,
    community,
    ROUND(AVG(readiness_pct), 1) AS avg_readiness_pct,
    MIN(readiness_pct) AS min_readiness_pct
FROM v_readiness
GROUP BY unit_id, unit_name, community;

CREATE OR REPLACE VIEW v_avg_readiness_by_equipment AS
SELECT
    equipment_type,
    ROUND(AVG(readiness_pct), 1) AS avg_readiness_pct
FROM v_readiness
GROUP BY equipment_type;

-- Training records join through personnel to reach unit -- a two-hop
-- relationship, unlike missions/readiness which relate to units directly.
-- This is the first measure in the semantic layer built from data that
-- originated in a genuinely different source (a JSON export, cleaned by a
-- separate ingestion path in pipeline/clean.py) rather than another CSV
-- shaped like the others.
CREATE OR REPLACE VIEW v_training_records AS
SELECT
    t.record_id,
    t.person_id,
    p.unit_id,
    u.unit_name,
    u.community,
    t.certification,
    t.completed_on_parsed AS completed_on,
    t.valid_months,
    (t.completed_on_parsed + (CAST(t.valid_months AS INTEGER) * INTERVAL 1 MONTH)) >= CURRENT_DATE AS is_current
FROM training_records t
JOIN personnel p ON t.person_id = p.person_id
JOIN units u ON p.unit_id = u.unit_id
WHERE t.is_valid_person = true
  AND t.completed_on_parsed IS NOT NULL
  AND t.valid_months IS NOT NULL;

-- Measure: training currency rate = share of certification records that are
-- still within their validity window as of today, out of all records where
-- currency could actually be determined (a record with a missing/invalid
-- valid_months, filtered out already by v_training_records above, is neither
-- current nor expired -- it's unknown, and unknown shouldn't count against
-- the rate any more than it should count for it).
CREATE OR REPLACE VIEW v_training_currency_by_unit AS
SELECT
    unit_id,
    unit_name,
    community,
    COUNT(*) AS certifications_evaluated,
    COUNT(*) FILTER (WHERE is_current) AS certifications_current,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_current) / NULLIF(COUNT(*), 0), 1) AS currency_rate_pct
FROM v_training_records
GROUP BY unit_id, unit_name, community;

CREATE OR REPLACE VIEW v_training_currency_by_certification AS
SELECT
    certification,
    COUNT(*) AS certifications_evaluated,
    COUNT(*) FILTER (WHERE is_current) AS certifications_current,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_current) / NULLIF(COUNT(*), 0), 1) AS currency_rate_pct
FROM v_training_records
GROUP BY certification;

-- Maintenance events are the third data source and the first ingested from
-- an actual SQL database (SQLite) rather than a flat file (see
-- pipeline/clean.py::clean_maintenance_events). equipment_type here uses
-- the SAME vocabulary as v_readiness's equipment_type -- a conformed
-- dimension across two independently-generated sources, not a coincidence.
CREATE OR REPLACE VIEW v_maintenance_events AS
SELECT
    mx.event_id,
    mx.unit_id,
    u.unit_name,
    u.community,
    mx.equipment_type,
    mx.discrepancy_type,
    mx.event_date_parsed AS event_date,
    mx.downtime_hours,
    mx.resolved_normalized AS resolved
FROM maintenance_events mx
JOIN units u ON mx.unit_id = u.unit_id
WHERE mx.is_valid_unit = true
  AND mx.event_date_parsed IS NOT NULL;

-- Measure: average discrepancy downtime by equipment type. Events with a
-- missing/previously-invalid (negative) downtime are excluded from the
-- average (AVG ignores nulls) rather than treated as zero downtime.
CREATE OR REPLACE VIEW v_maintenance_downtime_by_equipment AS
SELECT
    equipment_type,
    COUNT(*) AS discrepancy_count,
    ROUND(AVG(downtime_hours), 1) AS avg_downtime_hours,
    COUNT(*) FILTER (WHERE downtime_hours IS NULL) AS events_missing_downtime
FROM v_maintenance_events
GROUP BY equipment_type;

-- Measure: discrepancy resolution rate by unit = share of maintenance
-- events marked resolved, out of all events where resolution status is
-- actually known (events with a missing/unrecognized 'resolved' value are
-- excluded from the denominator, same "unknown isn't a no" principle as
-- the mission-completion and training-currency measures above).
CREATE OR REPLACE VIEW v_maintenance_resolution_rate_by_unit AS
SELECT
    unit_id,
    unit_name,
    community,
    COUNT(*) FILTER (WHERE resolved IS NOT NULL) AS events_with_known_status,
    COUNT(*) FILTER (WHERE resolved = true) AS events_resolved,
    ROUND(100.0 * COUNT(*) FILTER (WHERE resolved = true) / NULLIF(COUNT(*) FILTER (WHERE resolved IS NOT NULL), 0), 1) AS resolution_rate_pct
FROM v_maintenance_events
GROUP BY unit_id, unit_name, community;

-- ---------------------------------------------------------------------------
-- MULTIMODAL LAYER
-- Views over facts extracted from unstructured sources (free-text debriefs,
-- transcribed audio debriefs, photographed maintenance forms) by ingest/.
--
-- These sit in the same semantic layer as the structured measures above and
-- reuse the same equipment_type vocabulary, which is the entire point: an
-- extracted fact is only useful if it can be compared against a recorded
-- one, and that comparison is impossible if the two live in different
-- namespaces.
-- ---------------------------------------------------------------------------

-- Base view: extracted debrief facts joined to unit master data. Provenance
-- columns (source_modality, extracted_by, transcript_confidence) are carried
-- through deliberately rather than dropped after ingestion -- a downstream
-- consumer needs to be able to distinguish a fact typed by aircrew from one
-- inferred from a machine transcript.
CREATE OR REPLACE VIEW v_debrief_extractions AS
SELECT
    d.debrief_id,
    d.mission_id,
    d.unit_id,
    u.unit_name,
    u.community,
    d.source_modality,
    d.source_file,
    d.has_discrepancy,
    d.equipment_type,
    d.severity,
    d.phase,
    d.extracted_by,
    d.transcript_confidence
FROM debrief_extractions d
LEFT JOIN units u ON d.unit_id = u.unit_id;

-- Measure: how often each equipment type is implicated in debrief narratives.
-- This is a "what are crews actually reporting" measure, distinct from the
-- maintenance-record measures above, which capture what got written up in the
-- system of record. The two can legitimately disagree, and that disagreement
-- is the signal.
CREATE OR REPLACE VIEW v_debrief_mentions_by_equipment AS
SELECT
    equipment_type,
    COUNT(*) AS mention_count,
    COUNT(*) FILTER (WHERE severity = 'Major') AS major_count,
    COUNT(*) FILTER (WHERE severity = 'Moderate') AS moderate_count,
    COUNT(*) FILTER (WHERE severity = 'Minor') AS minor_count
FROM v_debrief_extractions
WHERE has_discrepancy = true AND equipment_type IS NOT NULL
GROUP BY equipment_type;

-- Measure: debrief-reported discrepancy rate by unit -- the share of a unit's
-- debriefs that describe an equipment problem at all.
CREATE OR REPLACE VIEW v_debrief_discrepancy_rate_by_unit AS
SELECT
    unit_id,
    unit_name,
    community,
    COUNT(*) AS debriefs_analyzed,
    COUNT(*) FILTER (WHERE has_discrepancy = true) AS debriefs_with_discrepancy,
    ROUND(100.0 * COUNT(*) FILTER (WHERE has_discrepancy = true) / NULLIF(COUNT(*), 0), 1) AS discrepancy_rate_pct
FROM v_debrief_extractions
WHERE unit_id IS NOT NULL
GROUP BY unit_id, unit_name, community;

-- Measure: extraction volume by modality and extractor. Operational
-- transparency rather than mission analytics -- it answers "where did the
-- unstructured facts in this warehouse come from, and what produced them,"
-- which is the provenance question an auditor asks first.
CREATE OR REPLACE VIEW v_extraction_provenance AS
SELECT
    source_modality,
    extracted_by,
    COUNT(*) AS record_count,
    ROUND(AVG(transcript_confidence), 3) AS avg_transcript_confidence
FROM v_debrief_extractions
GROUP BY source_modality, extracted_by;

-- Measure: CROSS-MODAL CORROBORATION.
-- Compares, per equipment type, what crews said in debriefs (unstructured)
-- against what the maintenance system recorded (structured). This is the
-- measure the multimodal work exists to make possible: neither source can
-- produce it alone.
--
-- The interesting cell is a large positive gap -- crews repeatedly reporting
-- problems with equipment that shows comparatively few maintenance write-ups,
-- which is a reporting-pipeline gap rather than an equipment fact. Presented
-- as counts and a ratio, deliberately NOT as an alert or a judgment: the
-- system's job is to surface the discrepancy between two sources, and a human
-- decides whether it reflects underreporting, differing thresholds for what
-- warrants a write-up, or nothing at all.
CREATE OR REPLACE VIEW v_narrative_vs_maintenance_corroboration AS
WITH narrative AS (
    SELECT equipment_type, COUNT(*) AS narrative_reports
    FROM v_debrief_extractions
    WHERE has_discrepancy = true AND equipment_type IS NOT NULL
    GROUP BY equipment_type
),
recorded AS (
    SELECT equipment_type, COUNT(*) AS maintenance_records
    FROM v_maintenance_events
    GROUP BY equipment_type
)
SELECT
    COALESCE(n.equipment_type, r.equipment_type) AS equipment_type,
    COALESCE(n.narrative_reports, 0) AS narrative_reports,
    COALESCE(r.maintenance_records, 0) AS maintenance_records,
    ROUND(
        1.0 * COALESCE(n.narrative_reports, 0)
        / NULLIF(COALESCE(r.maintenance_records, 0), 0),
    3) AS narrative_to_record_ratio
FROM narrative n
FULL OUTER JOIN recorded r ON n.equipment_type = r.equipment_type;
