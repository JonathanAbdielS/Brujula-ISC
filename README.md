# 🧭 Brújula ISC — Agente conversacional de la carrera

Agente de IA que orienta a aspirantes y estudiantes de **Ingeniería en Sistemas Computacionales del Instituto Tecnológico de Ciudad Guzmán (ITCG)**, plan ISIC-2010-224 con la especialidad **Tecnologías de la Inteligencia Artificial** (ISIE-TIA-2025-01). Además de conversar, ejecuta tres herramientas: consulta la retícula oficial, calcula el avance de créditos y orienta sobre la especialidad según los intereses del estudiante.

**URL del agente:** https://isc.jnhtn.com.mx
**Código:** este repositorio

---

## 1. Plataforma, herramientas y lenguaje

| Componente | Tecnología |
|---|---|
| Modelo de lenguaje | **Ollama** con `qwen2.5:7b` corriendo **localmente** en la VPS (sin APIs externas ni costo por uso) |
| Backend / agente | **Python 3 + FastAPI**, cliente `httpx` |
| Técnica de agente | *Function calling* (uso de herramientas) de Ollama en un bucle razonar → actuar → observar → responder |
| Base de conocimiento | Archivos JSON/Markdown en `data/`: retícula del ITCG con la especialidad, ligas a los programas oficiales, trámites y perfiles profesionales |
| Interfaz | HTML + CSS + JavaScript sin frameworks |
| Despliegue | VPS Hostinger KVM 8 · PM2 · HestiaCP (Nginx como proxy inverso + Let's Encrypt) |

### ¿Por qué es un agente y no sólo un chatbot?
El modelo **decide por sí mismo** cuándo necesita una herramienta, la ejecuta, lee el resultado y redacta la respuesta. Los datos (materias, créditos, porcentajes) salen de funciones deterministas en `app/tools.py`, no de la "memoria" del modelo, lo que evita que invente información. Cada respuesta muestra qué herramientas usó y con qué argumentos.

```
Usuario ──► FastAPI ──► Ollama (qwen2.5) ──¿necesita datos?──► herramienta (Python)
                              ▲                                     │
                              └────────── resultado JSON ◄──────────┘
                              │
                              └──► respuesta en lenguaje natural ──► Usuario
```

## 2. Tareas que realiza

1. **Conversación informativa** sobre la carrera: perfil de egreso, campo laboral, servicio social, residencia, titulación, inglés, a qué departamento acudir.
2. **`consultar_reticula`**: materias por semestre (1.º a 10.º), clave, créditos, horas (HT-HP-C) y liga al **programa oficial** de cualquier materia, y el resumen de créditos del plan.
3. **`calcular_avance`** (servicio extra): a partir de las materias o semestres aprobados calcula créditos, porcentaje, materias pendientes y si ya cumple los requisitos para servicio social (70 %) y residencia (80 % + servicio social).
4. **`recomendar_especialidad`** (servicio extra): explica la especialidad vigente y compara los intereses del estudiante con cinco perfiles profesionales (IA y datos, embebidos e IoT, web y móvil, redes y seguridad, software y bases de datos) para orientar su residencia, proyectos y formación.

## 3. Tipo de preguntas que se le pueden hacer

**Sobre la retícula**
- ¿Qué materias se llevan en 5.º semestre?
- ¿Cuántos créditos vale Lenguajes y Autómatas II y en qué semestre va?
- ¿Cuántos créditos tiene la carrera en total?
- ¿De qué trata Visión Artificial? (responde con la liga al programa oficial)

**Avance de créditos**
- Aprobé de 1.º a 6.º semestre y el servicio social, ¿cuánto llevo?
- Ya pasé todo hasta 4.º más POO y Química de nuevo… ¿ya puedo hacer servicio social?
- También se puede marcar materias en el panel **Mi retícula** y presionar **Calcular mi avance**.

**Especialidad**
- ¿Qué materias tiene la especialidad y en qué semestre se llevan?
- Me gustan los robots y la inteligencia artificial, ¿qué enfoque me conviene?
- Quiero trabajar en ciberseguridad, ¿qué materias me sirven?

**Trámites y orientación**
- ¿Qué necesito para hacer la residencia profesional?
- ¿Cuáles son los requisitos de titulación?
- ¿En qué puede trabajar un ingeniero en sistemas?

## 4. Guía de uso y ejecución

### Usarlo (en línea)
1. Abrir https://isc.jnhtn.com.mx
2. Escribir una pregunta o tocar una de las sugerencias.
3. (Opcional) En **Mi retícula** marcar las materias aprobadas y presionar **Calcular mi avance**. La barra y las materias se actualizan con el resultado del agente.
4. Debajo de cada respuesta, el apartado "El agente…" muestra qué herramienta usó y el resultado crudo.

### Ejecutarlo localmente
Requisitos: Python 3.10+ y [Ollama](https://ollama.com).
```bash
ollama pull qwen2.5:7b
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8010
# abrir http://localhost:8010
```

### Desplegarlo en la VPS
Guía detallada paso a paso en **[DEPLOY.md](DEPLOY.md)** (Ollama + PM2 + HestiaCP). Resumen:
1. `git clone` en `/opt/brujula-isc` y `bash deploy/setup.sh`.
2. En HestiaCP: agregar el dominio `isc.jnhtn.com.mx` con SSL de Let's Encrypt.
3. `sudo bash deploy/hestia/instalar-plantillas.sh` y elegir la plantilla `brujula` en el dominio.

### API
| Método | Ruta | Uso |
|---|---|---|
| `POST` | `/api/chat` | `{ "messages": [{"role":"user","content":"..."}] }` → `{ "respuesta", "herramientas" }` |
| `GET` | `/api/reticula` | Retícula en JSON |
| `GET` | `/api/health` | Estado del modelo |
| `GET` | `/docs` | Documentación interactiva (Swagger) generada por FastAPI |

## 5. Estructura
```
app/
  agent.py      bucle del agente y prompt de sistema
  tools.py      herramientas (lógica determinista)
  main.py       API FastAPI, límite de peticiones, archivos estáticos
  config.py     variables de entorno
data/
  reticula.json        plan ISIC-2010-224 + especialidad TIA, con ligas a programas
  carrera.md           información general y trámites
  especialidades.json  especialidad vigente y perfiles profesionales
static/                interfaz web
deploy/                PM2, script de instalación y plantillas de HestiaCP
docs/capturas/         evidencias de funcionamiento
```

## 6. Evidencias
Capturas en `docs/capturas/`:
1. Pantalla inicial.
2. Pregunta sobre un semestre (se resalta en la retícula).
3. Cálculo de avance (barra y materias en verde).
4. Respuesta sobre una materia con la liga a su programa oficial.
5. Orientación de especialidad (materias relacionadas subrayadas).
6. Detalle de herramientas usadas por el agente.

## Limitaciones y notas
- La retícula es la publicada por el ITCG; el orden por semestre es el sugerido. Los requisitos de trámites son lineamientos generales del TecNM y el agente siempre recomienda confirmarlos en el ITCG.
- La especialidad TIA está vigente de agosto 2025 a agosto 2027. Si cambia, basta con editar `data/reticula.json` y `data/especialidades.json`.
- El modelo corre en CPU: una respuesta tarda unos segundos. La primera pregunta tras un rato inactivo tarda más porque el modelo se carga en memoria.
