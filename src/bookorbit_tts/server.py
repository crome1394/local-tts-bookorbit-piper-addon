"""OpenAI-compatible TTS HTTP API for BookOrbit.

Routes:
    POST /v1/audio/speech     {"model","input","voice","speed","response_format"}
    GET  /v1/audio/voices     voice catalogue
    GET  /v1/models           used by BookOrbit's connection test
    GET  /health              liveness and engine information
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .audio import CONTENT_TYPES
from .config import Settings
from .engines import select_engine
from .logging_utils import silence_phonemizer
from .onnx_limits import limit_onnx_threads
from .synthesizer import ServerBusy, SynthesisError, Synthesizer

log = logging.getLogger(__name__)

_MAX_AUTH_HEADER = 512


class SpeechRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    model: str = Field(default="tts-1", max_length=64)
    input: str = Field(max_length=20_000)
    voice: str | None = Field(default=None, max_length=80)
    speed: float = 1.0
    response_format: str = Field(default="mp3", max_length=16)


class _BodyLimit:
    """Reject request bodies before they are decoded.

    Starlette does not cap body size. A client that can reach the port could
    otherwise pin memory with a multi-megabyte JSON document.
    """

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        declared = headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await _send_json(send, 413, {"detail": "request body is too large"})
                    return
            except ValueError:
                await _send_json(send, 400, {"detail": "invalid content-length"})
                return
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                return
            body = message.get("body", b"") or b""
            total += len(body)
            if total > self.max_bytes:
                await _send_json(send, 413, {"detail": "request body is too large"})
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        payload = b"".join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": payload, "more_body": False}

        await self.app(scope, replay, send)


async def _send_json(send, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _bearer_ok(authorization: str | None, api_key: str) -> bool:
    """Compare the bearer token without leaking the key through timing or logs."""
    if authorization is None or len(authorization) > _MAX_AUTH_HEADER:
        return False
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return False
    token = authorization[len(prefix) :]
    # Digests are fixed length, so a short or long token cannot skip the compare.
    return hmac.compare_digest(
        hashlib.sha256(token.encode("utf-8", "replace")).digest(),
        hashlib.sha256(api_key.encode("utf-8")).digest(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        # phonemizer logs a harmless word-alignment warning for every Kokoro
        # sentence; it would drown out the request log.
        silence_phonemizer()
        settings.ensure_dirs()
        limit_onnx_threads(settings.threads)
        if settings.exposed_without_key():
            log.warning(
                "listening on %s without %sAPI_KEY; anyone who can reach this port "
                "can consume CPU. Bind 127.0.0.1 or set an API key.",
                settings.host,
                "BOOKORBIT_TTS_",
            )
        started = time.perf_counter()
        engine, scores = select_engine(settings)
        synth = Synthesizer(engine, settings)
        app.state.synth = synth
        app.state.scores = scores
        app.state.started_at = time.time()
        log.info(
            "ready on %s:%s with engine=%s voices=%d (startup %.1fs)",
            settings.host,
            settings.port,
            engine.name,
            len(synth.voices()),
            time.perf_counter() - started,
        )
        try:
            yield
        finally:
            engine.close()

    app = FastAPI(
        title="BookOrbit TTS",
        version=__version__,
        description="Local, low-resource text to speech for BookOrbit",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs else None,
    )
    app.state.settings = settings
    app.add_middleware(_BodyLimit, max_bytes=settings.body_limit_bytes())

    def require_key(authorization: str | None = Header(default=None)) -> None:
        if not settings.api_key:
            return
        if not _bearer_ok(authorization, settings.api_key):
            raise HTTPException(status_code=401, detail="invalid API key")

    def synth_dependency() -> Synthesizer:
        return app.state.synth

    @app.get("/health")
    def health(synth: Synthesizer = Depends(synth_dependency)) -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "uptime_s": round(time.time() - app.state.started_at, 1),
            **synth.describe(),
        }

    @app.get("/")
    def index() -> dict:
        payload = {
            "name": "bookorbit-tts",
            "version": __version__,
            "bookorbit_base_url": f"http://<this-host>:{settings.port}/v1",
        }
        if settings.docs:
            payload["docs"] = "/docs"
        return payload

    @app.post("/v1/audio/speech", dependencies=[Depends(require_key)])
    def speech(body: SpeechRequest, synth: Synthesizer = Depends(synth_dependency)) -> Response:
        fmt = (body.response_format or "mp3").lower()
        if fmt not in CONTENT_TYPES:
            raise HTTPException(status_code=400, detail=f"unsupported response_format {fmt!r}")
        try:
            payload = synth.speak(body.input, body.voice, body.speed, fmt)
        except ServerBusy as exc:
            raise HTTPException(
                status_code=429, detail=str(exc), headers={"Retry-After": "2"}
            ) from exc
        except SynthesisError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception:
            # Engine failures can embed filesystem paths. Keep those in the log.
            log.exception("synthesis failed")
            raise HTTPException(status_code=503, detail="synthesis failed") from None
        return Response(
            content=payload,
            media_type=CONTENT_TYPES[fmt],
            headers={"X-TTS-Engine": synth.engine.name, "Cache-Control": "no-store"},
        )

    @app.get("/v1/audio/voices", dependencies=[Depends(require_key)])
    def voices(synth: Synthesizer = Depends(synth_dependency)) -> dict:
        return {
            "object": "list",
            "voices": [voice.to_dict() for voice in synth.voices()],
        }

    @app.get("/v1/models", dependencies=[Depends(require_key)])
    def models() -> dict:
        return {
            "object": "list",
            "data": [
                {"id": "tts-1", "object": "model", "owned_by": "bookorbit-tts"},
                {"id": "bookorbit-tts", "object": "model", "owned_by": "bookorbit-tts"},
            ],
        }

    return app
