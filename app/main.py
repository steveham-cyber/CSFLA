from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from api.routes import auth, imports, reports, admin

settings = get_settings()

app = FastAPI(
    title="CSFLA Research Application",
    docs_url="/docs" if settings.is_local else None,  # Disable Swagger in production
    redoc_url=None,
)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

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

# Security headers on every response
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

# Routes
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    # Never expose internal errors to the client
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})


@app.get("/health")
async def health():
    return {"status": "ok"}
