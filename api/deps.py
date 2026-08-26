"""
JWT-cookie auth for the API. auth/auth.py stays framework-agnostic (it only
knows about users.json/bcrypt/the audit log); this module is where "how a
session is carried between requests" actually lives, using a signed JWT in
an httpOnly cookie instead of Streamlit's server-side session state.

On the signing secret: set JWT_SECRET in the environment (or .env) for any
deployment where sessions need to survive a restart. When it's absent, a
random secret is generated per process rather than falling back to a
hardcoded one -- a known signing key committed to a repository is a real
vulnerability (anyone with the source can mint a valid admin session),
whereas a random per-process secret costs only that restarting the server
invalidates existing sessions, which for a local demo is a non-issue. This
also keeps rmf/SSP.md's CM-6 note honest: there is no default credential
shipping in this codebase.
"""
import os
import secrets
import sys
import warnings
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt
from fastapi import Depends, HTTPException, Request, status

from auth import auth

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_urlsafe(32)
    warnings.warn(
        "JWT_SECRET is not set; generated a random per-process signing secret. "
        "Sessions will be invalidated when this process restarts. Set JWT_SECRET "
        "in your environment or .env file for stable sessions.",
        stacklevel=2,
    )
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
