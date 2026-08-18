"""
Core authentication logic for the app: credential verification against
auth/users.json (bcrypt-hashed passwords) and an audit log of every
conversational query -- who asked what, when, and which interpreter
answered it.

This directly closes a gap GOVERNANCE_NOTES.md already named explicitly
under "Traceable": "Audit logging of who asked what and when (this
prototype has no user accounts, so there's no query history)." It's still
not enterprise identity management -- see rmf/SSP.md's IA control section
for exactly what's real here vs. what a production system would need
(DoD PKI/CAC, an actual IdP, password complexity/rotation policy, account
lockout, etc.). This is deliberately the minimum that makes "role-based
access" and "who did what" true statements instead of aspirational ones.

Framework-agnostic by design: this module knows nothing about Streamlit or
FastAPI. Session/cookie/token handling lives in the API layer (api/deps.py,
api/routers/auth.py), which calls verify_credentials() and load_users() here.
"""
import csv
import json
import os
from datetime import datetime

import bcrypt

USERS_PATH = os.path.join(os.path.dirname(__file__), "users.json")
AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "audit_log.csv")

ROLES_WITH_GOVERNANCE_ACCESS = {"admin"}


def load_users():
    if not os.path.exists(USERS_PATH):
        raise FileNotFoundError(
            f"{USERS_PATH} not found. Run `python3 auth/seed_users.py` once to create demo accounts."
        )
    with open(USERS_PATH) as f:
        return {u["username"]: u for u in json.load(f)}


def verify_credentials(username, password):
    """
    Returns the user record (username, role, display_name -- no password
    hash) if the credentials are valid, else None.
    """
    users = load_users()
    user = users.get(username)
    if user is None:
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return None
    return {"username": user["username"], "role": user["role"], "display_name": user["display_name"]}


def has_governance_access(role):
    return role in ROLES_WITH_GOVERNANCE_ACCESS


def log_query(username, role, question, understood, interpreted_by, caveat_count):
    """
    Appends one row to the audit log (data/audit_log.csv, gitignored) for
    every conversational query answered -- the "who asked what and when"
    record GOVERNANCE_NOTES.md flags as missing. Failing to write the log
    should never break the user-facing answer, so this is best-effort.
    """
    row = {
        "timestamp_utc": datetime.utcnow().isoformat(),
        "username": username or "unknown",
        "role": role or "unknown",
        "question": question,
        "understood": understood,
        "interpreted_by": interpreted_by,
        "caveat_count": caveat_count,
    }
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        file_exists = os.path.exists(AUDIT_LOG_PATH)
        with open(AUDIT_LOG_PATH, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except OSError:
        pass


def read_audit_log():
    import pandas as pd
    if not os.path.exists(AUDIT_LOG_PATH):
        return pd.DataFrame(columns=["timestamp_utc", "username", "role", "question", "understood", "interpreted_by", "caveat_count"])
    return pd.read_csv(AUDIT_LOG_PATH)
