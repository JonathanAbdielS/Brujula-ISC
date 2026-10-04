from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .agent import OllamaError, responder
from .tools import FUNCIONES, RETICULA

app = FastAPI(title="Brújula ISC", version="1.0.0",
              description="Agente conversacional de la carrera ISC del ITCG")


class Mensaje(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class Forzar(BaseModel):
    nombre: str
    argumentos: dict = {}


class ChatIn(BaseModel):
    messages: list[Mensaje] = Field(min_length=1)
    forzar: Forzar | None = None


# --- límite de peticiones por IP (en memoria, suficiente para una VPS) -------
_ventanas: dict[str, deque] = defaultdict(deque)


def _ip(request: Request) -> str:
    return (request.headers.get("x-real-ip")
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "?"))


def _limitar(ip: str) -> None:
    ahora, v = time.monotonic(), _ventanas[ip]
    while v and ahora - v[0] > 60:
        v.popleft()
    if len(v) >= config.RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Demasiadas preguntas en un minuto. Espera un momento y vuelve a intentar.")
    v.append(ahora)


# --- endpoints ---------------------------------------------------------------
@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    _limitar(_ip(request))
    if body.messages[-1].role != "user":
        raise HTTPException(400, "El último mensaje debe ser del usuario.")
    if body.forzar and body.forzar.nombre not in FUNCIONES:
        raise HTTPException(400, "Herramienta desconocida.")

    historial = [{"role": m.role, "content": m.content[: config.MAX_MESSAGE_CHARS]}
                 for m in body.messages[-config.MAX_HISTORY:]]
    try:
        return await responder(historial, body.forzar.model_dump() if body.forzar else None)
    except OllamaError:
        raise HTTPException(503, "El modelo no está disponible en este momento. Revisa que Ollama esté corriendo.")


@app.get("/api/reticula")
def reticula():
    return RETICULA


@app.get("/api/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            tags = (await c.get(f"{config.OLLAMA_URL}/api/tags")).json()
        modelos = [m["name"] for m in tags.get("models", [])]
        return {"ok": True, "modelo": config.OLLAMA_MODEL, "modelo_descargado": config.OLLAMA_MODEL in modelos}
    except Exception:
        return {"ok": False, "modelo": config.OLLAMA_MODEL, "detalle": "Ollama no responde"}


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")
