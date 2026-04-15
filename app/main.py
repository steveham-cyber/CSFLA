from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from api.routes import auth, imports, reports, admin, custom_reports
from api.routes import ui

settings = get_settings()

app = FastAPI(
    title="CSFLA Research Application",
    docs_url="/docs" if settings.is_local else None,  # Disable Swagger in production
    redoc_url=None,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=not settings.is_local,   # Secure flag on in production, off for local HTTP
    same_site="lax",                     # lax required for OAuth redirect to return session cookie
    max_age=3600,                        # 1-hour session lifetime
)

# Enforce HTTPS in production
if not settings.is_local:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Static files (CSS, JS)
# NOTE: chart.min.js must be placed at app/static/js/chart.min.js by the
# deployment process. Download from:
#   https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js
# Do NOT load Chart.js from a CDN — this would violate the Content-Security-Policy.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Content-Security-Policy:
# - default-src 'self'           — all other resource types locked to same origin
# - style-src 'self' + Google Fonts CSS + 'unsafe-inline' for Google Fonts @import
# - font-src 'self' + Google Fonts gstatic CDN
# - script-src 'self' + 'unsafe-inline' for inline Chart.js configuration blocks
#   (Chart.js itself is served from /static, not an external CDN)
# - img-src 'self' data:         — data: URIs needed for Chart.js canvas export
_CSP = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)

# Security headers on every response
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

# Routes — UI pages (no prefix, browser-facing HTML)
app.include_router(ui.router)

# Routes — JSON API
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(custom_reports.router, prefix="/api/custom-reports", tags=["custom-reports"])


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    # Never expose internal errors to the client
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})


@app.get("/health")
async def health():
    return {"status": "ok"}
