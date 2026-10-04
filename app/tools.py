"""Herramientas que el agente puede invocar (function calling de Ollama).

Toda la lógica es determinista: el modelo decide CUÁNDO usar una herramienta y
redacta la respuesta, pero los números (créditos, porcentajes, materias) salen de
aquí, no de la "memoria" del modelo.
"""
from __future__ import annotations

import difflib
import json
import re
import unicodedata
from typing import Any

from .config import DATA_DIR

RETICULA: dict = json.loads((DATA_DIR / "reticula.json").read_text("utf-8"))
ESPECIALIDADES: dict = json.loads((DATA_DIR / "especialidades.json").read_text("utf-8"))
MATERIAS: list[dict] = RETICULA["materias"]
CRED = RETICULA["creditos"]
TOTAL = CRED["total"]

_ROMANOS = {"1": "i", "2": "ii", "3": "iii"}


def normalizar(texto: str) -> str:
    """minúsculas, sin acentos ni signos, '2'->'ii', 'bases'->'base'."""
    t = unicodedata.normalize("NFD", str(texto).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    tokens = [_ROMANOS.get(tok, tok) for tok in t.split()]
    tokens = ["base" if tok == "bases" else tok for tok in tokens]
    return " ".join(tokens)


# Índice: nombre / clave / alias normalizado -> materia
_INDICE: dict[str, dict] = {}
for _m in MATERIAS:
    for _llave in [_m["nombre"], _m["clave"], *_m.get("alias", [])]:
        _INDICE[normalizar(_llave)] = _m


def resolver_materia(texto: str) -> dict | None:
    n = normalizar(texto)
    if not n:
        return None
    if n in _INDICE:
        return _INDICE[n]
    parecidas = difflib.get_close_matches(n, list(_INDICE), n=1, cutoff=0.78)
    return _INDICE[parecidas[0]] if parecidas else None


def _como_lista(valor: Any) -> list:
    """Los modelos pequeños a veces mandan 'a, b y c' en lugar de una lista."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    if isinstance(valor, str):
        return [p.strip() for p in re.split(r",|;|\n| y ", valor) if p.strip()]
    return [valor]


def _como_bool(valor: Any) -> bool:
    if isinstance(valor, str):
        return normalizar(valor) in {"true", "si", "yes", "1", "verdadero"}
    return bool(valor)


def _ficha(m: dict, con_url: bool = False) -> dict:
    f = {k: m[k] for k in ("clave", "nombre", "semestre", "creditos", "htp")}
    if m.get("especialidad"):
        f["especialidad"] = RETICULA["especialidad"]["nombre"]
    if con_url and m.get("programa_url"):
        f["programa_oficial"] = m["programa_url"]
    return f


# ---------------------------------------------------------------- herramienta 1
def consultar_reticula(semestre: Any = None, materia: str | None = None) -> dict:
    if materia:
        m = resolver_materia(materia)
        if not m:
            return {"encontrada": False, "busqueda": materia,
                    "sugerencia": "No está en la retícula genérica; puede ser una materia de especialidad."}
        companeras = [x["nombre"] for x in MATERIAS if x["semestre"] == m["semestre"] and x is not m]
        return {"encontrada": True, "materia": _ficha(m, con_url=True),
                "nota_htp": "HT-HP-créditos: horas teoría, horas práctica, créditos.",
                "mismo_semestre": companeras}

    if semestre not in (None, ""):
        try:
            s = int(semestre)
        except (TypeError, ValueError):
            return {"error": f"Semestre inválido: {semestre}"}
        if s == 10:
            return {"semestre": 10, "contenido": RETICULA["semestre_10"]}
        lista = [_ficha(m) for m in MATERIAS if m["semestre"] == s]
        if not lista:
            return {"error": f"La retícula va del semestre 1 al 10; no existe el {s}."}
        return {"semestre": s, "materias": lista, "creditos": sum(m["creditos"] for m in lista)}

    por_semestre = {}
    for m in MATERIAS:
        por_semestre.setdefault(m["semestre"], 0)
        por_semestre[m["semestre"]] += m["creditos"]
    return {"plan": RETICULA["plan"], "creditos": CRED, "especialidad": RETICULA["especialidad"],
            "creditos_por_semestre": por_semestre, "total_materias_genericas": len(MATERIAS)}


# ---------------------------------------------------------------- herramienta 2
def calcular_avance(materias_aprobadas: Any = None, semestres_completos: Any = None,
                    servicio_social: Any = False, residencia: Any = False,
                    actividades_complementarias: Any = False,
                    creditos_especialidad: Any = 0) -> dict:
    aprobadas: dict[str, dict] = {}
    no_reconocidas: list[str] = []

    for s in _como_lista(semestres_completos):
        try:
            s = int(s)
        except (TypeError, ValueError):
            continue
        for m in MATERIAS:
            if m["semestre"] == s:
                aprobadas[m["clave"]] = m

    for texto in _como_lista(materias_aprobadas):
        m = resolver_materia(str(texto))
        if m:
            aprobadas[m["clave"]] = m
        else:
            no_reconocidas.append(str(texto))

    try:
        esp_extra = max(0, int(creditos_especialidad or 0))  # p. ej. de una especialidad anterior
    except (TypeError, ValueError):
        esp_extra = 0
    ss, res, ac = _como_bool(servicio_social), _como_bool(residencia), _como_bool(actividades_complementarias)

    cred_materias = sum(m["creditos"] for m in aprobadas.values() if not m.get("especialidad"))
    esp = min(CRED["especialidad"],
              esp_extra + sum(m["creditos"] for m in aprobadas.values() if m.get("especialidad")))
    total = (cred_materias + esp + (CRED["servicio_social"] if ss else 0)
             + (CRED["residencia_profesional"] if res else 0)
             + (CRED["actividades_complementarias"] if ac else 0))
    pct = round(100 * total / TOTAL, 1)

    pendientes: dict[int, list[str]] = {}
    for m in MATERIAS:
        if m["clave"] not in aprobadas:
            pendientes.setdefault(m["semestre"], []).append(m["nombre"])

    return {
        "creditos_aprobados": total,
        "creditos_totales": TOTAL,
        "porcentaje": pct,
        "desglose": {
            "materias_genericas": f"{cred_materias}/{CRED['estructura_generica']}",
            "especialidad": f"{esp}/{CRED['especialidad']}",
            "servicio_social": ss, "residencia": res, "actividades_complementarias": ac,
        },
        "materias_aprobadas": len(aprobadas),
        "claves_aprobadas": sorted(aprobadas),
        "no_reconocidas": no_reconocidas,
        "pendientes_por_semestre": pendientes,
        "hitos": {
            "servicio_social": "ya acreditado" if ss else ("puede iniciarlo (>=70 % de créditos)" if pct >= 70 else "aún no: requiere 70 % de créditos"),
            "residencia": "ya acreditada" if res else (
                "cumple créditos y servicio social" if pct >= 80 and ss else
                "cumple el 80 % de créditos, pero falta acreditar el servicio social" if pct >= 80 else
                "aún no: requiere 80 % de créditos" + ("" if ss else " y el servicio social acreditado")),
            "nota": "Lineamientos generales TecNM; confirmar en el ITCG.",
        },
    }


# ---------------------------------------------------------------- herramienta 3
def recomendar_especialidad(intereses: Any = None) -> dict:
    vigente = ESPECIALIDADES["especialidad_vigente"]
    texto = " " + normalizar(" ".join(map(str, _como_lista(intereses)))) + " "
    todos = {normalizar(kw) for p in ESPECIALIDADES["perfiles"] for kw in p["palabras_clave"]
             if f" {normalizar(kw)} " in texto}
    # "redes neuronales" no debe contar también como "redes"
    validos = {k for k in todos if not any(k != o and f" {k} " in f" {o} " for o in todos)}
    ranking = []
    for perfil in ESPECIALIDADES["perfiles"]:
        hits = [kw for kw in perfil["palabras_clave"] if normalizar(kw) in validos]
        ranking.append((len(hits), hits, perfil))
    ranking.sort(key=lambda r: r[0], reverse=True)
    top = [r for r in ranking if r[0] > 0][:3]

    resultado = {"especialidad_vigente": vigente, "nota": ESPECIALIDADES["nota"]}
    if not top:
        resultado["perfiles_afines"] = []
        resultado["mensaje"] = ("No identifiqué intereses concretos. Pregunta qué disfruta "
                                "(programar apps, hardware, datos, redes, gestión…).")
        resultado["perfiles_disponibles"] = [p["nombre"] for p in ESPECIALIDADES["perfiles"]]
        return resultado
    resultado["perfiles_afines"] = [{
        "nombre": p["nombre"], "puntaje": score, "intereses_que_coinciden": hits,
        "descripcion": p["descripcion"], "materias_relacionadas": p["materias_relacionadas"],
        "campo_laboral": p["campo_laboral"],
    } for score, hits, p in top]
    return resultado


# ---------------------------------------------------------------- registro
FUNCIONES = {
    "consultar_reticula": consultar_reticula,
    "calcular_avance": calcular_avance,
    "recomendar_especialidad": recomendar_especialidad,
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "consultar_reticula",
        "description": "Consulta la retícula oficial de ISC: materias de un semestre, datos de una materia (clave, créditos, semestre) o el resumen de créditos de la carrera. Úsala SIEMPRE que pregunten por materias, semestres o créditos.",
        "parameters": {"type": "object", "properties": {
            "semestre": {"type": "integer", "description": "Número de semestre (1 a 10)."},
            "materia": {"type": "string", "description": "Nombre o clave de una materia."},
        }},
    }},
    {"type": "function", "function": {
        "name": "calcular_avance",
        "description": "Calcula créditos aprobados, porcentaje de avance, materias pendientes y si cumple requisitos de servicio social y residencia.",
        "parameters": {"type": "object", "properties": {
            "materias_aprobadas": {"type": "array", "items": {"type": "string"}, "description": "Nombres o claves de materias aprobadas sueltas (incluye las de especialidad)."},
            "semestres_completos": {"type": "array", "items": {"type": "integer"}, "description": "Semestres aprobados por completo, p. ej. [1,2,3]."},
            "servicio_social": {"type": "boolean", "description": "¿Ya acreditó el servicio social?"},
            "residencia": {"type": "boolean", "description": "¿Ya acreditó la residencia profesional?"},
            "actividades_complementarias": {"type": "boolean", "description": "¿Ya tiene los 5 créditos complementarios?"},
            "creditos_especialidad": {"type": "integer", "description": "Sólo si cursó materias de una especialidad ANTERIOR que no están en la retícula: sus créditos (0 a 25)."},
        }},
    }},
    {"type": "function", "function": {
        "name": "recomendar_especialidad",
        "description": "Explica la especialidad vigente (Tecnologías de la Inteligencia Artificial) y qué perfil profesional encaja mejor con los intereses del estudiante.",
        "parameters": {"type": "object", "properties": {
            "intereses": {"type": "array", "items": {"type": "string"}, "description": "Temas que le gustan, p. ej. ['robótica', 'inteligencia artificial']."},
        }, "required": ["intereses"]},
    }},
]


def ejecutar(nombre: str, argumentos: Any) -> dict:
    if isinstance(argumentos, str):
        try:
            argumentos = json.loads(argumentos or "{}")
        except json.JSONDecodeError:
            argumentos = {}
    funcion = FUNCIONES.get(nombre)
    if not funcion:
        return {"error": f"Herramienta desconocida: {nombre}"}
    validos = funcion.__code__.co_varnames[: funcion.__code__.co_argcount]
    limpios = {k: v for k, v in (argumentos or {}).items() if k in validos}
    try:
        return funcion(**limpios)
    except Exception as exc:  # el modelo nunca debe tumbar el servidor
        return {"error": f"Fallo al ejecutar {nombre}: {exc}"}
