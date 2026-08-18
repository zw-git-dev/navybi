"""
JWT-cookie auth for the API. auth/auth.py stays framework-agnostic (it only
knows about users.json/bcrypt/the audit log); this module is where "how a
session is carried between requests" actually lives, using a signed JWT in
an httpOnly cookie instead of Streamlit's server-side session state.

JWT_SECRET should be set via the environment for any real deployment -- the
fallback below is a clearly-labeled dev default, consistent with this
project's practice of never silently pretending a demo shortcut is
production-grade (see auth/auth.py's module docstring and rmf/SSP.md's IA
section).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt
from fastapi import Depends, HTTPException, Request, status

from auth import auth

JWT_SECRET = os.environ.get("JWT_SECRET", "navybi-dev-secret-DO-NOT-USE-IN-A-REAL-DEPLOYMENT")
JWT_ALGORITHM = "HS256"
COOKIE_NAME = "navybi_session"
TOKEN_LIFETIME = timedelta(hours=12)


def create_token(user):
    payload = {
        "sub": user["username"],
        "role": user["role"],
        "display_name": user["display_name"],
        "exp": datetime.now(timezone.utc) + TOKEN_LIFETIME,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return {
        "username": payload["sub"],
        "role": payload["role"],
        "display_name": payload["display_name"],
    }


def require_admin(user: dict = Depends(get_current_user)):
    if not auth.has_governance_access(user["role"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
