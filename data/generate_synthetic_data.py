"""
Generates a synthetic post-mission reporting dataset.

This is fabricated data for prototype purposes only -- no real unit, personnel,
or mission information. Intentional messiness (duplicates, nulls, inconsistent
formats, occasional orphan foreign keys) is injected on purpose so the
cleansing pipeline in pipeline/clean.py has real work to do and can be
demonstrated honestly rather than assumed.
"""
import csv
import json
import os
import random
import sqlite3
from datetime import datetime, timedelta

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "raw")
os.makedirs(OUT_DIR, exist_ok=True)

UNITS = [
    {"unit_id": "U01", "unit_name": "Strike Fighter Squadron 12", "community": "Strike Fighter", "home_base": "NAS Oceana", "lat": 36.8206, "lon": -76.0333},
    {"unit_id": "U02", "unit_name": "Helicopter Sea Combat Sqn 7", "community": "Rotary Wing", "home_base": "NAS North Island", "lat": 32.6997, "lon": -117.2153},
    {"unit_id": "U03", "unit_name": "Patrol Squadron 45", "community": "Maritime Patrol", "home_base": "NAS Jacksonville", "lat": 30.2358, "lon": -81.6801},
    {"unit_id": "U04", "unit_name": "Carrier Air Wing 3", "community": "Carrier Air Wing", "home_base": "NAS Oceana", "lat": 36.8206, "lon": -76.0333},
    {"unit_id": "U05", "unit_name": "Explosive Ordnance Disposal Mobile Unit 2", "community": "EOD", "home_base": "Joint Expeditionary Base Little Creek", "lat": 36.9126, "lon": -76.1833},
]

MISSION_TYPES = [
    "Air Intercept Training", "Close Air Support", "Maritime Patrol", "Search and Rescue",
    "Deck Landing Qualification", "EOD Render Safe", "Logistics Support", "ASW Training",
    "Strike Coordination", "Humanitarian Assistance",
]

STATUSES = ["Complete", "Complete", "Complete", "Partial", "Aborted"]

RANKS = ["ENS", "LTJG", "LT", "LCDR", "CDR", "PO1", "PO2", "PO3", "CPO"]

CERTIFICATIONS = [
    ("Water Survival", 24), ("CPR / First Aid", 12), ("NATOPS Check", 12),
    ("Weapons Qualification", 12), ("EOD Certification", 36), ("Damage Control", 24),
]

# Reuses the SAME equipment_type vocabulary as the readiness source (a
# conformed dimension across two independently-generated data sources) so
# a real "maintenance downtime vs. readiness" cross-source question is
# actually answerable, not just superficially plausible.
EQUIPMENT_TYPES = ["Primary Aircraft/Vehicle", "Comms Suite", "Sensor Package"]

DISCREPANCY_TYPES = ["Corrosion", "Electrical Fault", "Hydraulic Leak", "Software Glitch", "Structural Crack"]


def messy_date(d):
    """Return the same date in one of several inconsistent formats."""
    fmt = random.choice(["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"])
    return d.strftime(fmt)


def messy_datetime(d):
    """
    Simulates a *different* source system's export conventions than the CSV
    sources above -- an ISO date, a full ISO-8601 timestamp with a trailing
    'Z', or a plain date -- on purpose, so the training-records source is
    genuinely heterogeneous (a different format family, not just a copy of
    the CSV messiness) rather than only nominally "a second data source."
    """
    choice = random.random()
    if choice < 0.4:
        return d.strftime("%Y-%m-%d")
    elif choice < 0.7:
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return d.strftime("%m/%d/%Y")


def build_units():
    rows = []
    for u in UNITS:
        rows.append(u)
    return rows


def build_personnel(n=40):
    rows = []
    for i in range(n):
        unit = random.choice(UNITS)
        rows.append({
            "person_id": f"P{i:04d}",
            "unit_id": unit["unit_id"],
            "rank": random.choice(RANKS),
            "role": random.choice(["Pilot", "Aircrew", "Maintainer", "EOD Tech", "Intel", "Support"]),
            "name": fake.name(),
        })
    # inject a couple of duplicate personnel rows (same person_id re-entered)
    rows.append(dict(rows[3]))
    rows.append(dict(rows[10]))
    return rows


def build_missions(n=600):
    rows = []
    for i in range(n):
        unit = random.choice(UNITS)
        d = fake.date_between(start_date="-180d", end_date="today")
        status = random.choice(STATUSES)
        objective_met = None
        if status == "Complete":
            objective_met = random.choice([True, True, True, False])
        elif status == "Partial":
            objective_met = random.choice([True, False])
        # Aborted missions leave objective_met as None (null) -- realistic gap in reporting

        lat_jitter = unit["lat"] + random.uniform(-1.5, 1.5)
        lon_jitter = unit["lon"] + random.uniform(-1.5, 1.5)

        row = {
            "mission_id": f"M{i:05d}",
            "unit_id": unit["unit_id"],
            "mission_type": random.choice(MISSION_TYPES),
            "mission_date": messy_date(d),
            "status": status,
            "objective_met": objective_met,
            "duration_hours": round(random.uniform(0.5, 12.0), 1),
            "lat": round(lat_jitter, 4),
            "lon": round(lon_jitter, 4),
        }

        # inject occasional messiness
        roll = random.random()
        if roll < 0.03:
            row["unit_id"] = "U99"  # orphan FK -- unit that doesn't exist
        if roll < 0.05:
            row["duration_hours"] = None  # missing value
        if roll < 0.02:
            row["duration_hours"] = -row["duration_hours"] if row["duration_hours"] else -1.0  # bad outlier

        rows.append(row)

    # inject exact-duplicate mission rows (double-reported missions)
    for _ in range(15):
        rows.append(dict(random.choice(rows[:n])))

    # inject inconsistent unit_id casing on a few rows to test normalization
    for _ in range(10):
        r = random.choice(rows[:n])
        dup = dict(r)
        dup["mission_id"] = dup["mission_id"] + "_lc"
        dup["unit_id"] = dup["unit_id"].lower()
        rows.append(dup)

    return rows


def build_readiness(months=6):
    rows = []
    rid = 0
    for u in UNITS:
        for m in range(months):
            for equip in ["Primary Aircraft/Vehicle", "Comms Suite", "Sensor Package"]:
                pct = round(random.uniform(55, 100), 1)
                # inject a bad outlier occasionally
                if random.random() < 0.03:
                    pct = round(random.uniform(101, 140), 1)  # impossible >100%
                rows.append({
                    "record_id": f"R{rid:05d}",
                    "unit_id": u["unit_id"],
                    "equipment_type": equip,
                    "month_index": m,
                    "readiness_pct": pct,
                })
                rid += 1
    return rows


def build_training_records(personnel_rows, n=180):
    """
    A training/certification records source, simulating an export from a
    separate training-management system rather than the same post-mission
    reporting database as missions/readiness. Deliberately a different file
    format (JSON, not CSV) and a different messiness profile (timestamp
    format variety, orphan person references, garbage validity periods)
    to make the "connect to heterogeneous data sources" requirement mean
    something concrete rather than importing the same shape of file twice.
    """
    person_ids = [p["person_id"] for p in personnel_rows]
    rows = []
    for i in range(n):
        person_id = random.choice(person_ids)
        cert_name, valid_months = random.choice(CERTIFICATIONS)
        completed = fake.date_between(start_date="-700d", end_date="today")
        completed_dt = datetime.combine(completed, datetime.min.time())

        row = {
            "record_id": f"T{i:04d}",
            "person_id": person_id,
            "certification": cert_name,
            "completed_on": messy_datetime(completed_dt),
            "valid_months": valid_months,
        }

        roll = random.random()
        if roll < 0.04:
            row["person_id"] = "P9999"  # orphan FK -- personnel record that doesn't exist
        if roll < 0.05:
            row["valid_months"] = None  # missing validity period
        if roll < 0.02:
            row["valid_months"] = -valid_months  # garbage negative value

        rows.append(row)

    # inject duplicate training records (same certification re-submitted for the same person/date)
    for _ in range(8):
        rows.append(dict(random.choice(rows[:n])))

    return rows


def build_maintenance_events(n=220):
    """
    A maintenance/discrepancy log, simulating an export from an actual SQL
    maintenance-tracking database rather than another flat file -- the
    generated data is loaded straight into a SQLite database (see
    write_sqlite() / main()) so pipeline/clean.py has to connect and query it
    like a real SQL source, not just parse another text format. This is what
    makes the "SQL databases" part of the data-source-breadth requirement
    concrete rather than another CSV/JSON variant.

    The 'resolved' field is deliberately stored as inconsistent text
    ("1"/"0", "Y"/"N", "true"/"false", NULL) -- exactly the kind of messiness
    a real SQL table with no enforced boolean type and multiple data-entry
    eras tends to accumulate, and different in KIND from the messiness in
    the other three sources (which is about dates/formats/duplicates, not
    inconsistent value encodings for the same logical field).
    """
    resolved_encodings = ["1", "0", "Y", "N", "true", "false", None]
    rows = []
    for i in range(n):
        unit = random.choice(UNITS)
        equipment_type = random.choice(EQUIPMENT_TYPES)
        d = fake.date_between(start_date="-365d", end_date="today")
        downtime = round(random.uniform(0.5, 48.0), 1)

        row = {
            "event_id": f"MX{i:04d}",
            "unit_id": unit["unit_id"],
            "equipment_type": equipment_type,
            "event_date": messy_date(d),
            "discrepancy_type": random.choice(DISCREPANCY_TYPES),
            "downtime_hours": downtime,
            "resolved": random.choice(resolved_encodings),
        }

        roll = random.random()
        if roll < 0.03:
            row["unit_id"] = "U99"  # orphan FK -- unit that doesn't exist
        if roll < 0.03:
            row["downtime_hours"] = -downtime  # garbage negative value

        rows.append(row)

    # inject duplicate maintenance events (same discrepancy logged twice)
    for _ in range(10):
        rows.append(dict(random.choice(rows[:n])))

    return rows


def write_sqlite(path, table_name, rows):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    cols = sorted({k for r in rows for k in r.keys()})
    con.execute(f"CREATE TABLE {table_name} ({', '.join(cols)})")
    placeholders = ", ".join("?" for _ in cols)
    con.executemany(
        f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})",
        [[r.get(c) for c in cols] for r in rows],
    )
    con.commit()
    con.close()


def write_csv(path, rows):
    if not rows:
        return
    keys = sorted({k for r in rows for k in r.keys()})
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def write_json(path, rows):
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)


def main():
    units = build_units()
    personnel = build_personnel()
    missions = build_missions()
    readiness = build_readiness()
    training = build_training_records(personnel)
    maintenance = build_maintenance_events()

    write_csv(os.path.join(OUT_DIR, "units.csv"), units)
    write_csv(os.path.join(OUT_DIR, "personnel.csv"), personnel)
    write_csv(os.path.join(OUT_DIR, "missions.csv"), missions)
    write_csv(os.path.join(OUT_DIR, "readiness.csv"), readiness)
    write_json(os.path.join(OUT_DIR, "training_records.json"), training)
    write_sqlite(os.path.join(OUT_DIR, "maintenance.db"), "maintenance_events", maintenance)

    print(f"Wrote {len(units)} units, {len(personnel)} personnel rows, "
          f"{len(missions)} mission rows, {len(readiness)} readiness rows, "
          f"{len(training)} training records (JSON), "
          f"{len(maintenance)} maintenance events (SQLite) to {OUT_DIR}")


if __name__ == "__main__":
    main()
