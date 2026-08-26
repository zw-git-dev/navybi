import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from api.routers import ask, audit, auth, dashboard, governance  # noqa: E402

app = FastAPI(title="NavyBI API")

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

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


# --- serving the built frontend (production mode) -----------------------
#
# In development the Vite dev server serves the SPA on :5173 and proxies /api
# here, so this block does nothing (frontend/dist won't exist). Once
# `npm run build` has produced frontend/dist, the same Uvicorn process serves
# the app and the API on one origin -- which removes CORS from the picture
# entirely and makes the cookie plainly first-party.
#
# Registered last, deliberately: the catch-all below must not shadow any /api
# route, and FastAPI resolves in registration order.
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        """
        Returns index.html for any non-API path so client-side routing works
        on a hard refresh or a pasted deep link (/governance, /ask, ...). A
        real file is served when one exists, so favicon.svg and friends still
        resolve. Unknown /api/* paths get a JSON 404 rather than the HTML
        shell -- handing an API caller a page of markup makes debugging
        needlessly confusing.
        """
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)

        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
