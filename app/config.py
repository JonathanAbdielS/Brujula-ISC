import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))
_ka = os.getenv("OLLAMA_KEEP_ALIVE", "-1")          # -1 = dejar el modelo siempre cargado en RAM
KEEP_ALIVE = int(_ka) if _ka.lstrip("-").isdigit() else _ka

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "12"))          # mensajes previos que se envían al modelo
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "1500"))
MAX_TOOL_STEPS = int(os.getenv("MAX_TOOL_STEPS", "4"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "12"))

DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
