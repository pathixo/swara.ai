import sys
import os
from dotenv import load_dotenv

def get_base_path():
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_app_data_path():
    """Get writable path for logs and config"""
    if getattr(sys, 'frozen', False):
        path = os.path.join(os.getenv('APPDATA'), 'Antigravity', 'Jarvis')
    else:
        path = os.path.dirname(os.path.abspath(__file__))
    
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path

# Load env from AppData if frozen, else local
load_dotenv()

# ─────────────────────── LLM Provider Config ────────────────────────────────
# Active provider: "ollama" | "gemini" | "groq" | "grok"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Ollama Configuration (Local Brain)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")

# Ollama Model Auto-Selection
# When enabled, Jarvis picks the fast model for simple queries and the logic
# model for complex reasoning / code tasks.
OLLAMA_FAST_MODEL  = os.getenv("OLLAMA_FAST_MODEL",  "gemma:2b")       # speed
OLLAMA_LOGIC_MODEL = os.getenv("OLLAMA_LOGIC_MODEL", "llama3.2:3b")    # reasoning
OLLAMA_AUTO_SELECT = os.getenv("OLLAMA_AUTO_SELECT", "true").lower() == "true"

# Gemini Configuration (Google Cloud)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Groq Configuration (Groq Cloud — fast inference)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Grok Configuration (xAI Cloud)
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-3-mini-fast")

# ─────────────────────── Wake Word & Audio ──────────────────────────────────
# Porcupine (Wake Word) API Key
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")

# Porcupine Model Path
PORCUPINE_MODEL_PATH = os.getenv("PORCUPINE_MODEL_PATH", "")

# Default Wake Word
WAKE_WORD = "jarvis"

# TTS Voice
TTS_VOICE = "en-US-GuyNeural"

# Default Persona
DEFAULT_PERSONA = os.getenv("DEFAULT_PERSONA", "witty")

# ─────────────────────── Paths ──────────────────────────────────────────────
BASE_DIR = get_base_path()
DATA_DIR = get_app_data_path()
LOGS_DIR = os.path.join(DATA_DIR, "logs")

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)
