"""QuantPilot Backend Proxy — FastAPI entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.audit import AuditLogMiddleware
from app.core.metrics import MetricsMiddleware, metrics_endpoint
from app.core.tracing import install_tracing
from app.api import auth, google, ai, versions, admin, dashboard, slo, policy

app = FastAPI(
    title="QuantPilot Backend Proxy",
    version="0.1.0",
    description="Google API + AI + versioning proxy for QuantPilot SPA.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(MetricsMiddleware)

# OpenTelemetry (opt-in via QP_OTEL_ENABLED)
install_tracing(app)

app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(google.router,   prefix="/google",   tags=["google"])
app.include_router(ai.router,       prefix="/ai",       tags=["ai"])
app.include_router(versions.router, prefix="/versions", tags=["versions"])
app.include_router(admin.router,    prefix="/admin",    tags=["admin"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(slo.router,       prefix="/dashboard", tags=["slo"])
app.include_router(policy.router,    prefix="/policy",    tags=["policy"])


@app.get("/health")
def health():
    return {"ok": True, "service": "quantpilot-backend", "version": "0.1.0"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_endpoint()
