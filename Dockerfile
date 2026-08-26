# Multi-stage: build the SPA with Node, then serve it (and the API) from a
# single Python image. The Node toolchain doesn't ship in the final image --
# only the built bundle does.

FROM node:22-slim AS frontend-build
WORKDIR /build

# Copy manifests first so a dependency install layer can be cached
# independently of source changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY app/ ./app/
COPY auth/ ./auth/
COPY data/ ./data/
COPY pipeline/ ./pipeline/
COPY warehouse/ ./warehouse/
COPY docker-entrypoint.sh ./

COPY --from=frontend-build /build/dist ./frontend/dist

# Runs as a non-root user; the app writes generated data, the DuckDB
# warehouse, seeded users, and the audit log, so those paths need to be owned
# by that user rather than root.
RUN useradd --create-home --uid 10001 navybi \
    && chmod +x docker-entrypoint.sh \
    && mkdir -p data/raw data/clean var \
    && chown -R navybi:navybi /app
USER navybi

EXPOSE 8000

# A healthcheck against the API rather than the SPA shell -- the shell is a
# static file that would return 200 even if the warehouse were broken.
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
