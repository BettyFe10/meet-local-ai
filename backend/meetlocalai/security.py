"""Protezioni del backend locale.

- Host check (anti DNS-rebinding): solo 127.0.0.1:<porta> o localhost:<porta>.
- Origin: consentite solo pagine dell'estensione (chrome-extension://<id>); siti web -> 403.
  Se backend.allowed_extension_ids è vuoto (fase di sviluppo) si accetta qualsiasi estensione e lo si segnala nei log.
- Header X-MeetLocalAI obbligatorio sulle API: forza il preflight CORS e blocca le "simple request" dai siti.
"""

from __future__ import annotations

import logging
import re

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import messages

log = logging.getLogger("meetlocalai.security")

CLIENT_HEADER = "x-meetlocalai"
# Il tag <audio> del browser non può inviare header: l'audio si scarica con un token temporaneo
# ottenuto prima tramite una chiamata API normale (con header). Il token viene validato dall'endpoint.
_AUDIO_PATH_RE = re.compile(r"^/api/v1/meetings/[^/]+/audio$")
EXT_PREFIX = "chrome-extension://"


def _deny(code: str) -> JSONResponse:
    return JSONResponse(status_code=403, content={"error_code": code, "user_message": messages.FORBIDDEN, "detail_logged": True})


class SecurityPolicy:
    def __init__(self, port: int, allowed_extension_ids: list[str]):
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.allowed_ids = set(allowed_extension_ids)
        if not self.allowed_ids:
            log.warning("allowed_extension_ids vuoto: accettata qualsiasi estensione Chrome (modalità sviluppo).")

    def origin_allowed(self, origin: str | None) -> bool:
        if origin is None:
            return True  # client locali senza Origin (curl, script di diagnosi)
        if not origin.startswith(EXT_PREFIX):
            return False
        ext_id = origin[len(EXT_PREFIX):].rstrip("/")
        return bool(ext_id) and (not self.allowed_ids or ext_id in self.allowed_ids)

    def cors_headers(self, origin: str) -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-MeetLocalAI",
            "Access-Control-Max-Age": "600",
        }

    async def __call__(self, request: Request, call_next):
        host = request.headers.get("host", "")
        if host not in self.allowed_hosts:
            log.warning("Richiesta rifiutata: Host non consentito (%s)", host[:100])
            return _deny("forbidden_host")
        origin = request.headers.get("origin")
        if not self.origin_allowed(origin):
            log.warning("Richiesta rifiutata: Origin non consentita (%s)", (origin or "")[:100])
            return _deny("forbidden_origin")
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=self.cors_headers(origin) if origin else {})
        media_with_token = (request.method == "GET" and _AUDIO_PATH_RE.match(request.url.path)
                            and request.query_params.get("token"))
        if request.url.path.startswith("/api/") and request.headers.get(CLIENT_HEADER) != "1" and not media_with_token:
            log.warning("Richiesta rifiutata: header %s mancante (%s)", CLIENT_HEADER, request.url.path)
            return _deny("missing_client_header")
        response = await call_next(request)
        if origin:
            for k, v in self.cors_headers(origin).items():
                response.headers[k] = v
        return response
