import logging
import mimetypes
import os
import warnings
from pathlib import Path

# Suppress harmless GenAI SDK cleanup error (_async_httpx_client missing)
warnings.filterwarnings("ignore", message=".*_async_httpx_client.*")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

mimetypes.add_type("audio/wav", ".wav")  # noqa: E402 — must run before StaticFiles mounts

from ..config import settings  # noqa: E402, I001
from ..db.client import ping as db_ping  # noqa: E402
from .routes import (  # noqa: E402, I001
    agent_work,
    assets,
    coverage,
    dictation as dictation_routes,
    goals,
    history,
    rewrite,
    screenplay,
    scripts,
    system,
    table_read,
)
from .ws import agents, dictation  # noqa: E402

_PROTO_ENABLED = os.getenv("GREENLIGHT_ENABLE_PROTO", "false").lower() == "true"

logger = logging.getLogger(__name__)

app = FastAPI(title="Greenlight", version="0.1.0")

from .auth import FirebaseAuthMiddleware, auth_enabled  # noqa: E402

app.add_middleware(FirebaseAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    # Prod frontend calls the API origin directly (bypasses Firebase Hosting's
    # 60s rewrite timeout); local dev uses the Vite proxy origins.
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "https://greenlight15488.web.app",
        "https://greenlight15488.firebaseapp.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scripts.router, prefix="/api", tags=["scripts"])
app.include_router(screenplay.router, prefix="/api", tags=["screenplay"])
app.include_router(system.router, prefix="/api", tags=["system"])
app.include_router(coverage.router, prefix="/api", tags=["coverage"])
app.include_router(table_read.router, prefix="/api", tags=["table-read"])
app.include_router(rewrite.router, prefix="/api", tags=["rewrite"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(goals.router, prefix="/api", tags=["goals"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(dictation_routes.router, prefix="/api", tags=["dictation"])
app.include_router(agent_work.router, prefix="/api", tags=["agent-work"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(dictation.router, prefix="/api", tags=["dictation-ws"])

if _PROTO_ENABLED:
    from .routes import proto  # noqa: E402

    app.include_router(proto.router, prefix="/api", tags=["proto"])
    logger.warning("greenlight /api/proto/* ENABLED — experimental routes exposed")


@app.on_event("startup")
async def _startup_warning():
    host = settings.api_host
    if host not in ("127.0.0.1", "::1", "localhost"):
        logger.warning(
            f"greenlight API binding to {host} — exposed beyond loopback. "
            "Demo posture is local-only; set API_HOST=127.0.0.1 to suppress."
        )
    from ..config import validate_runtime

    validate_runtime()


@app.get("/api/health")
async def health():
    db_ok = db_ping()
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status": "ok" if db_ok else "degraded",
            "db": db_ok,
            "version": "0.1.0",
        },
    )


generated_audio = Path("generated_audio")
# Prod (auth on) serves audio from GCS public URLs — the disk mount is a
# dev/test convenience and must never expose files unauthenticated: the auth
# middleware only guards /api paths, a static mount would bypass it entirely.
if generated_audio.exists() and not auth_enabled():

    class NoCacheStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope=None):  # type: ignore[override]
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "no-store"
            return response

    app.mount(
        "/generated_audio",
        NoCacheStaticFiles(directory=str(generated_audio)),
        name="audio",
    )
elif generated_audio.exists():
    logger.info("auth enabled — skipping /generated_audio static mount (GCS serves audio)")

WEB_DIST_ROOT = (Path(__file__).parent.parent / "web" / "dist").resolve()
if WEB_DIST_ROOT.exists():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path:
            candidate = (WEB_DIST_ROOT / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(WEB_DIST_ROOT):
                response = FileResponse(candidate)
                response.headers["Cache-Control"] = "no-cache, must-revalidate"
                return response
        response = FileResponse(WEB_DIST_ROOT / "index.html")
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response
