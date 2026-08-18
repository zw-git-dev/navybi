import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

load_dotenv()

from api.routers import ask, audit, auth, dashboard, governance  # noqa: E402

app = FastAPI(title="NavyBI API")

FRONTEND_ORIGINS = os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Dashboard/drill-down/audit-log responses are JSON arrays of a few hundred
# rows -- cheap to compute but noticeably smaller over the wire once
# gzipped. min_size skips compressing tiny responses where the gzip framing
# overhead would outweigh the savings.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(ask.router)
app.include_router(governance.router)
app.include_router(audit.router)


@app.get("/api/health")
def health():
    return {"ok": True}
