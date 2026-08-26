import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends

from api.deps import require_admin
from api.utils import df_to_records
from auth import auth as auth_core

router = APIRouter(prefix="/api/audit-log", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("")
def audit_log():
    df = auth_core.read_audit_log()
    if df.empty:
        return []
    # Must go through df_to_records, not a bare to_dict(): a logged question
    # the app didn't understand has interpreted_by=None, which round-trips
    # through the CSV as a pandas NaN. Serializing that raises
    # "Out of range float values are not JSON compliant" and 500s this
    # endpoint -- meaning one unrecognized question would permanently break
    # the audit log page, which is exactly the record that's supposed to be
    # dependable. Caught by tests/test_api.py.
    return df_to_records(df.sort_values("timestamp_utc", ascending=False))
