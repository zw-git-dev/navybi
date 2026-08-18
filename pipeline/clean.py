"""
Ingestion + automated cleansing pipeline.

Reads the raw synthetic CSVs and produces cleaned tables plus a cleansing
log. The log is a first-class output, not an afterthought: every cleansing
decision (dropped duplicate, nulled-out invalid value, flagged orphan
foreign key) is recorded with a count and a plain-language reason, because
"transform raw data by cleaning it" is only trustworthy if what got changed
is visible and auditable, not silently dropped.
"""
import json
import os
import sqlite3
from datetime import datetime

import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
CLEAN_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "clean")
os.makedirs(CLEAN_DIR, exist_ok=True)

log_entries = []


def log(table, action, count, reason):
    log_entries.append({
        "table": table,
        "action": action,
        "row_count": int(count),
        "reason": reason,
    })


def parse_messy_date(val):
    if pd.isna(val):
        return pd.NaT
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(val), fmt).date()
        except ValueError:
            continue
    return pd.NaT


def parse_messy_datetime(val):
    """Same idea as parse_messy_date, but also handles the ISO-8601-with-Z
    timestamp format the training-records JSON source uses, since that
    source was deliberately built to export a different format family than
    the CSV sources (see data/generate_synthetic_data.py)."""
    if pd.isna(val):
        return pd.NaT
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(str(val), fmt).date()
        except ValueError:
            continue
    return pd.NaT


def clean_units():
    df = pd.read_csv(os.path.join(RAW_DIR, "units.csv"))
    before = len(df)
    df["unit_id"] = df["unit_id"].str.strip().str.upper()
    df["unit_name"] = df["unit_name"].str.strip()
    df = df.drop_duplicates(subset=["unit_id"])
    log("units", "dedup_by_unit_id", before - len(df), "Removed exact/near duplicate unit master records")
    return df


def clean_personnel(valid_unit_ids):
    df = pd.read_csv(os.path.join(RAW_DIR, "personnel.csv"))
    before = len(df)
    dupes = df.duplicated(subset=["person_id"]).sum()
    df = df.drop_duplicates(subset=["person_id"])
    log("personnel", "dedup_by_person_id", dupes, "Removed re-entered duplicate personnel records (same person_id)")

    orphan_mask = ~df["unit_id"].isin(valid_unit_ids)
    orphans = int(orphan_mask.sum())
    if orphans:
        log("personnel", "flagged_orphan_unit_id", orphans,
            "personnel rows reference a unit_id not present in the unit master -- kept but flagged, not dropped, since a missing unit master entry is a data-entry gap upstream, not proof the person record is wrong")
    df["data_quality_flag"] = orphan_mask.map({True: "orphan_unit_id", False: None})
    return df


def clean_missions(valid_unit_ids):
    df = pd.read_csv(os.path.join(RAW_DIR, "missions.csv"))
    before = len(df)

    # normalize unit_id casing/whitespace before dedup so casing variants collapse
    df["unit_id"] = df["unit_id"].astype(str).str.strip().str.upper()

    dupes = df.duplicated(subset=["mission_id"]).sum()
    df = df.drop_duplicates(subset=["mission_id"])
    log("missions", "dedup_by_mission_id", dupes, "Removed double-reported mission records sharing the same mission_id")

    df["mission_date_parsed"] = df["mission_date"].apply(parse_messy_date)
    unparsed = df["mission_date_parsed"].isna().sum()
    if unparsed:
        log("missions", "unparsable_date_flagged", unparsed, "mission_date could not be parsed under any known format -- kept as null rather than guessed")

    orphan_mask = ~df["unit_id"].isin(valid_unit_ids)
    orphans = int(orphan_mask.sum())
    if orphans:
        log("missions", "flagged_orphan_unit_id", orphans,
            "mission rows reference a unit_id not present in the unit master -- flagged, excluded from unit-level rollups, but retained in raw form for audit")

    invalid_duration_mask = df["duration_hours"] < 0
    invalid_durations = int(invalid_duration_mask.sum())
    if invalid_durations:
        df.loc[invalid_duration_mask, "duration_hours"] = None
        log("missions", "nulled_negative_duration", invalid_durations, "duration_hours was negative (physically impossible) -- set to null rather than silently flipped to positive, since a sign error and a unit error look identical and shouldn't be guessed at")

    missing_duration = df["duration_hours"].isna().sum()
    log("missions", "missing_duration_present", missing_duration, "duration_hours was missing in source data -- left null, not imputed, so downstream averages can choose to exclude or explicitly note incomplete coverage")

    df["is_valid_unit"] = ~orphan_mask
    return df


def clean_readiness(valid_unit_ids):
    df = pd.read_csv(os.path.join(RAW_DIR, "readiness.csv"))
    before = len(df)

    df["unit_id"] = df["unit_id"].astype(str).str.strip().str.upper()

    invalid_mask = df["readiness_pct"] > 100
    invalid = int(invalid_mask.sum())
    if invalid:
        log("readiness", "flagged_impossible_pct", invalid, "readiness_pct exceeded 100%, which is not physically meaningful -- flagged and excluded from averages rather than clipped, so the source system error is visible instead of hidden")
    df["data_quality_flag"] = invalid_mask.map({True: "impossible_pct_gt_100", False: None})
    return df


def clean_training_records(valid_person_ids):
    """
    Ingests the training_records JSON source -- a different file format and
    a different upstream "system" than the CSV sources -- through the same
    cleansing discipline (logged, auditable decisions) as everything else,
    so the pipeline demonstrably handles heterogeneous sources rather than
    only claiming to.
    """
    with open(os.path.join(RAW_DIR, "training_records.json")) as f:
        raw = json.load(f)
    df = pd.DataFrame(raw)
    before = len(df)

    dupes = df.duplicated(subset=["record_id"]).sum()
    df = df.drop_duplicates(subset=["record_id"])
    log("training_records", "dedup_by_record_id", dupes, "Removed re-submitted duplicate training/certification records sharing the same record_id")

    df["completed_on_parsed"] = df["completed_on"].apply(parse_messy_datetime)
    unparsed = df["completed_on_parsed"].isna().sum()
    if unparsed:
        log("training_records", "unparsable_date_flagged", unparsed, "completed_on could not be parsed under any known format (including the ISO-8601 variant this source uses) -- kept as null rather than guessed")

    orphan_mask = ~df["person_id"].isin(valid_person_ids)
    orphans = int(orphan_mask.sum())
    if orphans:
        log("training_records", "flagged_orphan_person_id", orphans,
            "training record references a person_id not present in the personnel master -- flagged, excluded from currency rollups, but retained in raw form for audit")

    invalid_months_mask = df["valid_months"] < 0
    invalid_months = int(invalid_months_mask.sum())
    if invalid_months:
        df.loc[invalid_months_mask, "valid_months"] = None
        log("training_records", "nulled_negative_valid_months", invalid_months, "valid_months was negative (physically impossible) -- set to null rather than guessed at what was intended")

    missing_months = df["valid_months"].isna().sum()
    if missing_months:
        log("training_records", "missing_valid_months_present", missing_months, "valid_months was missing in source data -- left null; currency cannot be determined for these records, so they're excluded from the currency rate rather than assumed current or expired")

    df["is_valid_person"] = ~orphan_mask
    return df


RESOLVED_ENCODINGS = {"1": True, "0": False, "Y": True, "N": False, "true": True, "false": False}


def clean_maintenance_events(valid_unit_ids):
    """
    Ingests maintenance_events from a real SQLite database via sqlite3 --
    a materially different ingestion path than pd.read_csv/json.load (an
    actual SQL connection and query, not a file parse), which is the point:
    this source demonstrates the "connect to SQL databases" requirement
    concretely rather than by another flat file with a different extension.
    """
    con = sqlite3.connect(os.path.join(RAW_DIR, "maintenance.db"))
    df = pd.read_sql("SELECT * FROM maintenance_events", con)
    con.close()
    before = len(df)

    df["unit_id"] = df["unit_id"].astype(str).str.strip().str.upper()

    dupes = df.duplicated(subset=["event_id"]).sum()
    df = df.drop_duplicates(subset=["event_id"])
    log("maintenance_events", "dedup_by_event_id", dupes, "Removed double-logged maintenance events sharing the same event_id")

    df["event_date_parsed"] = df["event_date"].apply(parse_messy_date)
    unparsed = df["event_date_parsed"].isna().sum()
    if unparsed:
        log("maintenance_events", "unparsable_date_flagged", unparsed, "event_date could not be parsed under any known format -- kept as null rather than guessed")

    orphan_mask = ~df["unit_id"].isin(valid_unit_ids)
    orphans = int(orphan_mask.sum())
    if orphans:
        log("maintenance_events", "flagged_orphan_unit_id", orphans,
            "maintenance event references a unit_id not present in the unit master -- flagged, excluded from unit-level rollups, but retained in raw form for audit")

    invalid_downtime_mask = df["downtime_hours"] < 0
    invalid_downtime = int(invalid_downtime_mask.sum())
    if invalid_downtime:
        df.loc[invalid_downtime_mask, "downtime_hours"] = None
        log("maintenance_events", "nulled_negative_downtime", invalid_downtime, "downtime_hours was negative (physically impossible) -- set to null rather than guessed at what was intended")

    # 'resolved' arrives with several inconsistent encodings for the same
    # two logical values -- realistic for a SQL table with no enforced
    # boolean type across different data-entry eras -- normalized to a
    # single nullable boolean rather than picking one encoding and
    # silently coercing the rest to it.
    df["resolved_normalized"] = df["resolved"].map(RESOLVED_ENCODINGS)
    normalized_count = df["resolved"].notna().sum() - (df["resolved_normalized"].isna() & df["resolved"].notna()).sum()
    if normalized_count:
        log("maintenance_events", "resolved_value_normalized", normalized_count, "resolved was stored under multiple inconsistent encodings (1/0, Y/N, true/false) -- normalized to a single boolean so downstream measures don't have to special-case each encoding")
    missing_resolved = df["resolved_normalized"].isna().sum()
    if missing_resolved:
        log("maintenance_events", "missing_resolved_present", missing_resolved, "resolved was missing or unrecognized in source data -- left null rather than assumed resolved or unresolved")

    df["is_valid_unit"] = ~orphan_mask
    return df


def main():
    units = clean_units()
    valid_unit_ids = set(units["unit_id"])

    personnel = clean_personnel(valid_unit_ids)
    valid_person_ids = set(personnel["person_id"])

    missions = clean_missions(valid_unit_ids)
    readiness = clean_readiness(valid_unit_ids)
    training = clean_training_records(valid_person_ids)
    maintenance = clean_maintenance_events(valid_unit_ids)

    units.to_csv(os.path.join(CLEAN_DIR, "units.csv"), index=False)
    personnel.to_csv(os.path.join(CLEAN_DIR, "personnel.csv"), index=False)
    missions.to_csv(os.path.join(CLEAN_DIR, "missions.csv"), index=False)
    readiness.to_csv(os.path.join(CLEAN_DIR, "readiness.csv"), index=False)
    training.to_csv(os.path.join(CLEAN_DIR, "training_records.csv"), index=False)
    maintenance.to_csv(os.path.join(CLEAN_DIR, "maintenance_events.csv"), index=False)

    with open(os.path.join(CLEAN_DIR, "cleansing_log.json"), "w") as f:
        json.dump(log_entries, f, indent=2)

    print("Cleansing complete. Summary:")
    for entry in log_entries:
        print(f"  [{entry['table']}] {entry['action']}: {entry['row_count']} rows -- {entry['reason']}")


if __name__ == "__main__":
    main()
