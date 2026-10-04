"""Bucle del agente: modelo local (Ollama) + herramientas.

razonar -> (¿necesito una herramienta?) -> ejecutar -> observar -> responder
"""
from __future__ import annotations

import json
from datetime import date

import httpx

from . import config
from .tools import TOOL_SCHEMAS, ejecutar

CARRERA_MD = (config.DATA_DIR / "carrera.md").read_text("utf-8")

SYSTEM_PROMPT = f"""Eres Brújula ISC, el asistente de la carrera de Ingeniería en Sistemas Computacionales del Instituto Tecnológico de Ciudad Guzmán (ITCG). Fecha de hoy: {date.today().isoformat()}.

Tu trabajo: orientar a aspirantes y estudiantes sobre la carrera, su retícula, créditos, trámites y especialidad.

Reglas:
1. Responde siempre en español, claro y breve (máximo ~150 palabras salvo que pidan detalle). Puedes usar listas cortas con guiones y **negritas**.
2. Para materias, semestres, claves o créditos USA la herramienta consultar_reticula. No inventes materias ni créditos.
3. Si el estudiante dice qué materias o semestres aprobó, o pregunta cuánto lleva, USA calcular_avance y explica el resultado (créditos, porcentaje y si ya puede hacer servicio social o residencia).
4. La única especialidad vigente es Tecnologías de la Inteligencia Artificial. Si preguntan qué especialidad o enfoque les conviene, USA recomendar_especialidad con sus intereses (si no los dijo, pregúntaselos primero) y explica cómo encaja su perfil con la especialidad; no digas que existen otras especialidades.
5. Si preguntan de qué trata una materia o su temario, usa consultar_reticula con esa materia y comparte la liga del programa oficial como [Programa oficial](url).
6. Para trámites usa la información de abajo y aclara que son lineamientos generales que deben confirmarse en el departamento indicado.
7. Si no sabes algo (fechas de inscripción, costos, nombres de maestros), dilo y sugiere a qué departamento acudir. Nunca inventes.
8. Si te preguntan algo ajeno a la carrera, contesta en una frase y regresa al tema.

Información de la carrera:
{CARRERA_MD}
"""


class OllamaError(RuntimeError):
    pass


async def _chat(client: httpx.AsyncClient, messages: list[dict], usar_tools: bool) -> dict:
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": config.KEEP_ALIVE,
        "options": {"num_ctx": config.NUM_CTX, "temperature": config.TEMPERATURE},
    }
    if usar_tools:
        payload["tools"] = TOOL_SCHEMAS
    try:
        r = await client.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaError(f"No se pudo contactar a Ollama: {exc}") from exc
    return r.json()["message"]


def _registrar(messages: list[dict], log: list[dict], nombre: str, args) -> None:
    resultado = ejecutar(nombre, args)
    log.append({"nombre": nombre, "argumentos": args, "resultado": resultado})
    messages.append({"role": "tool", "tool_name": nombre,
                     "content": json.dumps(resultado, ensure_ascii=False)})


async def responder(historial: list[dict], forzar: dict | None = None) -> dict:
    """historial: [{'role': 'user'|'assistant', 'content': str}, ...]
    forzar: {'nombre': str, 'argumentos': dict} -> ejecuta esa herramienta antes de llamar al modelo
            (lo usa el botón 'Calcular mi avance' para no depender de que un modelo pequeño acierte).
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *historial]
    log: list[dict] = []

    async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT) as client:
        if forzar:
            messages.append({"role": "assistant", "content": "",
                             "tool_calls": [{"function": {"name": forzar["nombre"],
                                                          "arguments": forzar.get("argumentos", {})}}]})
            _registrar(messages, log, forzar["nombre"], forzar.get("argumentos", {}))

        for _ in range(config.MAX_TOOL_STEPS):
            msg = await _chat(client, messages, usar_tools=True)
            llamadas = msg.get("tool_calls") or []
            if not llamadas:
                return {"respuesta": (msg.get("content") or "").strip(), "herramientas": log}
            messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": llamadas})
            for llamada in llamadas:
                fn = llamada.get("function", {})
                _registrar(messages, log, fn.get("name", ""), fn.get("arguments", {}))

        # demasiados pasos: pedir respuesta final sin herramientas
        msg = await _chat(client, messages, usar_tools=False)
        return {"respuesta": (msg.get("content") or "").strip(), "herramientas": log}
