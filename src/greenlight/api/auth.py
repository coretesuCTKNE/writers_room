"""Firebase Auth (anonymous sign-in) — request-scoped principal.

FIREBASE_PROJECT_ID empty = auth off: every request passes through with
principal "local" (local dev + the whole test suite).

Auth on:
- REST /api/* requires Authorization: Bearer <idToken> (except /api/health);
  invalid/missing -> 401.
- WebSockets require ?token=<idToken> before the upgrade is accepted
  (browsers cannot set WS headers).
- Non-/api paths (SPA statics) always pass.

Pure ASGI middleware (not BaseHTTPMiddleware) so the contextvar set here
propagates into the request handler — BaseHTTPMiddleware runs downstream in
a separate task and would lose it.
"""

import json
import logging
from urllib.parse import unquote

from starlette.concurrency import run_in_threadpool

from ..config import settings
from .services.script_repo.state import principal_var

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/api/health"}

_admin_initialized = False


def auth_enabled() -> bool:
    return bool(settings.firebase_project_id)


def _init_admin() -> None:
    global _admin_initialized
    if _admin_initialized:
        return
    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, options={"projectId": settings.firebase_project_id})
    _admin_initialized = True


def verify_token(token: str) -> str | None:
    """Return the uid for a valid Firebase ID token, else None."""
    try:
        _init_admin()
        from firebase_admin import auth as fb_auth

        claims = fb_auth.verify_id_token(token)
        return claims.get("uid")
    except Exception as e:
        logger.warning(f"Auth token rejected: {e}")
        return None


def _token_from_ws_scope(scope) -> str:
    qs = scope.get("query_string", b"").decode()
    for pair in qs.split("&"):
        if pair.startswith("token="):
            return unquote(pair[6:])
    return ""


def _token_from_http_scope(scope) -> str:
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            authz = value.decode()
            if authz.lower().startswith("bearer "):
                return authz[7:]
    return ""


async def _send_json_401(send) -> None:
    payload = json.dumps({"detail": "Authentication required"}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": payload})


class FirebaseAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not auth_enabled() or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if scope["type"] == "http" and (not path.startswith("/api") or path in EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            token = _token_from_ws_scope(scope)
        else:
            token = _token_from_http_scope(scope)

        uid = await run_in_threadpool(verify_token, token) if token else None
        if not uid:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                await _send_json_401(send)
            return

        principal_var.set(uid)
        await self.app(scope, receive, send)
