"""
tux.ai API — FastAPI (REST) + gRPC server (chat streaming).

Both servers start in the same asyncio event loop so they share the connection
pool and loaded model state.
"""
import asyncio
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import get_settings
from api.limiter import limiter
from api.routers import admin, auth, chats

logger = logging.getLogger("tuxai")

settings = get_settings()

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="tux.ai API", docs_url=None, redoc_url=None)  # disable docs in prod
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "connect-src 'self' http://localhost:8080; "  # Envoy gRPC-Web
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "          # Tailwind needs this
        "img-src 'self' data:;"
    )
    return response


@app.middleware("http")
async def csrf_protect(request: Request, call_next) -> Response:
    """Validate CSRF token for state-changing requests on REST endpoints."""
    if request.method in ("POST", "DELETE", "PATCH", "PUT") and request.url.path.startswith("/api"):
        # gRPC handled by Envoy; skip OPTIONS pre-flights
        if request.method != "OPTIONS":
            cookie_csrf = request.cookies.get("csrf_token", "")
            header_csrf = request.headers.get("X-CSRF-Token", "")
            # Allow auth/login through without CSRF (first request has no token yet)
            if not request.url.path.endswith("/login"):
                if not cookie_csrf or cookie_csrf != header_csrf:
                    from fastapi.responses import JSONResponse
                    return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)
    return await call_next(request)


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(chats.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── gRPC server lifecycle ──────────────────────────────────────────────────────

_grpc_server = None


@app.on_event("startup")
async def start_grpc():
    global _grpc_server
    try:
        from api.grpc.chat_servicer import create_grpc_server
        _grpc_server = create_grpc_server(settings.GRPC_PORT)
        await _grpc_server.start()
        logger.info("gRPC server started on port %d", settings.GRPC_PORT)
    except Exception as exc:
        logger.warning("gRPC server could not start: %s", exc)


@app.on_event("shutdown")
async def stop_grpc():
    if _grpc_server:
        await _grpc_server.stop(grace=5)
