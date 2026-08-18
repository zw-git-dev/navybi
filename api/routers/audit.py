import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, Depends

from api.deps import require_admin
from auth import auth as auth_core

router = APIRouter(prefix="/api/audit-log", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("")
def audit_log():
    df = auth_core.read_audit_log()
    if df.empty:
        return []
    return df.sort_values("timestamp_utc", ascending=False).to_dict(orient="records")
