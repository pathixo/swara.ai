"""
Brain Module — Multi-Provider LLM Interface Layer
===================================================
Provides a unified interface to multiple LLM backends:
  - Ollama  (local, default)
  - Gemini  (Google Cloud)
  - Groq    (Groq Cloud — fast inference)
  - Grok    (xAI Cloud)

Supports conversation memory, chain-of-thought reasoning, retry logic,
provider failover, and structured settings management.
"""

import logging
import json
import re
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from Jarvis.core.personas import PersonaManager
from Jarvis.core.context import ContextManager

import requests

from Jarvis.config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_FAST_MODEL,
    OLLAMA_LOGIC_MODEL,
    OLLAMA_CODE_MODEL,
    OLLAMA_AUTO_SELECT,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROK_API_KEY,
    GROK_MODEL,
    LLM_PROVIDER,
    DEFAULT_PERSONA,
)

logger = logging.getLogger("jarvis.brain")


# ─────────────────────────── Constants ──────────────────────────────────────

class Provider(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"
    GROQ   = "groq"
    GROK   = "grok"


DEFAULT_SYSTEM_PROMPT = (
    "You are Jarvis, an autonomous AI desktop assistant. You MUST respond using structured tags for any system action.\n\n"
    "## Perceived Latency Reduction (CRITICAL)\n"
    "To provide an 'instant' experience, you MUST always speak a conversational acknowledgment BEFORE any tags. This gives the user immediate feedback while the system prepares the task.\n"
    "*Example*: 'I'm on it, sir. [SHELL]Get-Process[/SHELL]'\n\n"
    "## Execution Protocol\n"
    "You EXECUTE tasks — never just describe them. If you can act, ACT. If you can't, say so in one sentence and offer a brief alternative.\n\n"
    "## Response Templates (STRICT ADHERENCE REQUIRED)\n"
    "1. **Action Mode** (for all tasks): Immediate conversational confirmation FIRST, then the tag.\n"
    "   *Example*: 'Opening Chrome, sir. [ACTION]launch_app: chrome[/ACTION]'\n"
    "2. **Conversational Mode** (no tasks): Respond naturally, NO tags, no fabricated actions.\n"
    "   *Example*: 'The weather in London is currently 15 degrees and overcast, sir.'\n\n"
    "## Rules\n"
    "1. To launch an app: [ACTION]launch_app: <app_name>[/ACTION]\n"
    "2. To open a URL: [ACTION]open_url: <url>[/ACTION]\n"
    "3. To run a shell command: [SHELL]<command>[/SHELL]\n"
    "4. To get system info: [ACTION]system_info[/ACTION]\n"
    "5. To play music or search media: [ACTION]play_music: <query>[/ACTION]\n"
    "6. To execute Python code securely: [ACTION]exec_code: <python_code>[/ACTION]\n"
    "7. For dangerous commands (shutdown, format, delete), ask for confirmation FIRST.\n"
    "8. **No Silence**: NEVER leave the user without a response. If an action fails or isn't possible, acknowledge it immediately. 'I'm afraid I couldn't find Spotify installed, sir.'\n\n"
    "## Safety\n"
    "- Destructive commands: warn and ask confirmation FIRST.\n"
    "- Safe commands: execute immediately.\n"
    "- Never hallucinate paths or flags."
)


# ─────────────────────────── Settings ───────────────────────────────────────

@dataclass
class BrainSettings:
    """Immutable-ish config snapshot; centralizes all tuning knobs."""
    provider: str = "ollama"
    model: str = OLLAMA_MODEL
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 512
    timeout: int = 60
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_history: int = 20  # conversation memory window

    def validate_temperature(self, value: float) -> bool:
        return 0.0 <= value <= 2.0

    def validate_top_p(self, value: float) -> bool:
        return 0.0 < value <= 1.0

    def validate_max_tokens(self, value: int) -> bool:
        return value > 0

    def validate_timeout(self, value: int) -> bool:
        return value > 0


# ──────────────────────── Conversation Memory ───────────────────────────────

@dataclass
class Message:
    role: str       # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)


class ConversationMemory:
    """Sliding-window conversation buffer for multi-turn context."""

    def __init__(self, max_messages: int = 20):
        self._messages: list[Message] = []
        self._max = max_messages

    def add(self, role: str, content: str) -> None:
        self._messages.append(Message(role=role, content=content))
        # Trim oldest (keep system prompt if present)
        if len(self._messages) > self._max:
            self._messages = self._messages[-self._max:]

    def get_history(self) -> list[dict]:
        """Return history in OpenAI-compatible format."""
        return [{"role": m.role, "content": m.content} for m in self._messages]

    def clear(self) -> None:
        self._messages.clear()

    @property
    def length(self) -> int:
        return len(self._messages)


# ──────────────────────── Provider Backends ─────────────────────────────────

class _OllamaBackend:
    """Ollama local LLM via REST API."""

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")
        self._generate_url = f"{self._url}/api/generate"
        self._chat_url = f"{self._url}/api/chat"

    def generate(self, settings: BrainSettings, prompt: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": settings.system_prompt}]
        for msg in history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": settings.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "num_predict": settings.max_tokens,
            },
        }

        resp = requests.post(self._chat_url, json=payload, timeout=settings.timeout)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    def generate_stream(self, settings: BrainSettings, prompt: str, history: list[dict]):
        """Yield response tokens from Ollama's chat API."""
        messages = [{"role": "system", "content": settings.system_prompt}]
        for msg in history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": settings.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "num_predict": settings.max_tokens,
            },
        }

        resp = requests.post(self._chat_url, json=payload, stream=True, timeout=settings.timeout)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
                if data.get("done"):
                    break

    def health_check(self) -> bool:
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> tuple[bool, list[str] | str]:
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            r.raise_for_status()
            models = r.json().get("models", [])
            names = [m.get("name") for m in models if m.get("name")]
            return True, names
        except Exception as e:
            return False, f"Could not fetch local models: {e}"


class _GeminiBackend:
    """Google Gemini via REST API (no SDK dependency)."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def generate(self, settings: BrainSettings, prompt: str, history: list[dict]) -> str:
        if not self._api_key:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY in .env")

        model = settings.model if settings.provider == "gemini" else GEMINI_MODEL
        url = f"{self.BASE_URL}/{model}:generateContent?key={self._api_key}"

        # Build messages
        contents = []

        # Add system instruction as first user/model exchange
        contents.append({
            "role": "user",
            "parts": [{"text": f"[SYSTEM INSTRUCTION]\n{settings.system_prompt}"}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Understood. I am Jarvis, ready to assist."}]
        })

        # Add conversation history
        for msg in history[-8:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        # Add current prompt
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": settings.temperature,
                "topP": settings.top_p,
                "maxOutputTokens": settings.max_tokens,
            },
        }

        resp = requests.post(url, json=payload, timeout=settings.timeout)

        # Handle rate limiting with retry-after
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            logger.warning("Gemini rate limited, waiting %ds...", retry_after)
            time.sleep(min(retry_after, 10))  # Wait up to 10s
            resp = requests.post(url, json=payload, timeout=settings.timeout)

        resp.raise_for_status()

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            error_info = data.get("error", {})
            raise ValueError(f"Gemini returned no candidates: {error_info}")

        parts = candidates[0].get("content", {}).get("parts", [])
        return parts[0].get("text", "") if parts else ""

    def generate_stream(self, settings: BrainSettings, prompt: str, history: list[dict]):
        """Yield response tokens from Gemini's streaming SSE endpoint."""
        if not self._api_key:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY in .env")

        model = settings.model if settings.provider == "gemini" else GEMINI_MODEL
        url = f"{self.BASE_URL}/{model}:streamGenerateContent?key={self._api_key}&alt=sse"

        contents = []
        contents.append({
            "role": "user",
            "parts": [{"text": f"[SYSTEM INSTRUCTION]\n{settings.system_prompt}"}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Understood. I am Jarvis, ready to assist."}]
        })
        for msg in history[-8:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": settings.temperature,
                "topP": settings.top_p,
                "maxOutputTokens": settings.max_tokens,
            },
        }

        resp = requests.post(url, json=payload, stream=True, timeout=settings.timeout)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode() if isinstance(line, bytes) else line
            if line.startswith("data: "):
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    parts = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [])
                    )
                    text = parts[0].get("text", "") if parts else ""
                    if text:
                        yield text
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            url = f"{self.BASE_URL}?key={self._api_key}"
            r = requests.get(url, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> tuple[bool, list[str] | str]:
        if not self._api_key:
            return False, "Gemini API key not configured."
        try:
            url = f"{self.BASE_URL}?key={self._api_key}"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            models = r.json().get("models", [])
            names = [m.get("name", "").replace("models/", "") for m in models]
            return True, names
        except Exception as e:
            return False, f"Could not fetch Gemini models: {e}"


class _GroqBackend:
    """Groq Cloud via OpenAI-compatible REST API (fast inference)."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def generate(self, settings: BrainSettings, prompt: str, history: list[dict]) -> str:
        if not self._api_key:
            raise ValueError("Groq API key not configured. Set GROQ_API_KEY in .env")

        model = settings.model if settings.provider == "groq" else GROQ_MODEL

        messages = [{"role": "system", "content": settings.system_prompt}]

        for msg in history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(self.BASE_URL, json=payload, headers=headers, timeout=settings.timeout)
        resp.raise_for_status()

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"Groq returned no choices: {data}")

        return choices[0].get("message", {}).get("content", "")

    def generate_stream(self, settings: BrainSettings, prompt: str, history: list[dict]):
        """Yield tokens from Groq's OpenAI-compatible SSE streaming endpoint."""
        if not self._api_key:
            raise ValueError("Groq API key not configured. Set GROQ_API_KEY in .env")

        model = settings.model if settings.provider == "groq" else GROQ_MODEL
        messages = [{"role": "system", "content": settings.system_prompt}]
        for msg in history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            self.BASE_URL, json=payload, headers=headers,
            stream=True, timeout=settings.timeout,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode() if isinstance(line, bytes) else line
            if line.startswith("data: "):
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    delta = data["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            r = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> tuple[bool, list[str] | str]:
        if not self._api_key:
            return False, "Groq API key not configured."
        try:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            r = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=10)
            r.raise_for_status()
            models = r.json().get("data", [])
            names = [m.get("id", "") for m in models]
            return True, names
        except Exception as e:
            return False, f"Could not fetch Groq models: {e}"


class _GrokBackend:
    """xAI Grok via OpenAI-compatible REST API."""

    BASE_URL = "https://api.x.ai/v1/chat/completions"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def generate(self, settings: BrainSettings, prompt: str, history: list[dict]) -> str:
        if not self._api_key:
            raise ValueError("Grok API key not configured. Set GROK_API_KEY in .env")

        model = settings.model if settings.provider == "grok" else GROK_MODEL

        messages = [{"role": "system", "content": settings.system_prompt}]

        for msg in history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(self.BASE_URL, json=payload, headers=headers, timeout=settings.timeout)
        resp.raise_for_status()

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"Grok returned no choices: {data}")

        return choices[0].get("message", {}).get("content", "")

    def generate_stream(self, settings: BrainSettings, prompt: str, history: list[dict]):
        """Yield tokens from xAI Grok's OpenAI-compatible SSE streaming endpoint."""
        if not self._api_key:
            raise ValueError("Grok API key not configured. Set GROK_API_KEY in .env")

        model = settings.model if settings.provider == "grok" else GROK_MODEL
        messages = [{"role": "system", "content": settings.system_prompt}]
        for msg in history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            self.BASE_URL, json=payload, headers=headers,
            stream=True, timeout=settings.timeout,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode() if isinstance(line, bytes) else line
            if line.startswith("data: "):
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    delta = data["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            r = requests.get("https://api.x.ai/v1/models", headers=headers, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> tuple[bool, list[str] | str]:
        if not self._api_key:
            return False, "Grok API key not configured."
        try:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            r = requests.get("https://api.x.ai/v1/models", headers=headers, timeout=10)
            r.raise_for_status()
            models = r.json().get("data", [])
            names = [m.get("id", "") for m in models]
            return True, names
        except Exception as e:
            return False, f"Could not fetch Grok models: {e}"


# ─────────────────────────── Brain ──────────────────────────────────────────

class Brain:
    """
    Industry-grade LLM interface with multi-provider support,
    conversation memory, retry logic, and provider failover.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    def __init__(self, provider: Optional[str] = None):
        # Persona system
        self.personas = PersonaManager(default=DEFAULT_PERSONA)
        active_persona = self.personas.get_active()

        self.settings = BrainSettings(
            provider=provider or LLM_PROVIDER,
            model=self._default_model_for(provider or LLM_PROVIDER),
            system_prompt=active_persona.system_prompt,
        )
        self.memory = ConversationMemory(max_messages=self.settings.max_history)
        self.context = ContextManager()

        # Initialize all backends (lazy — they only call APIs when used)
        self._backends = {
            Provider.OLLAMA: _OllamaBackend(OLLAMA_URL),
            Provider.GEMINI: _GeminiBackend(GEMINI_API_KEY),
            Provider.GROQ:   _GroqBackend(GROQ_API_KEY),
            Provider.GROK:   _GrokBackend(GROK_API_KEY),
        }

        logger.info(
            "Brain initialized | provider=%s | model=%s | persona=%s",
            self.settings.provider, self.settings.model, active_persona.name,
        )
        print(f"Brain initialized | provider={self.settings.provider} | model={self.settings.model} | persona={active_persona.name}")

        # Warm up: Load default model in background to reduce first-query latency
        if self.settings.provider == Provider.OLLAMA:
            threading.Thread(target=self._warm_up, daemon=True).start()

    def _warm_up(self):
        """Pre-load the model into memory."""
        try:
            logger.info("Warming up Ollama model: %s", self.settings.model)
            # Send a minimal prompt just to trigger loading
            self.generate_response("hi", history=[])
            logger.info("Ollama model warmed up.")
        except Exception as e:
            logger.warning("Warm-up failed: %s", e)

    # ── Public API ──────────────────────────────────────────────────────────

    # Patterns for different task categories
    _CODE_PATTERNS = [
        r"\b(python|script|code|program|function|class|module|debug|fix|refactor|implement|syntax|error|traceback)\b",
        r"\b(write|create|develop|generate)\s+(a\s+)?(script|program|app|function)\b",
        r"\b(how\s+to)\s+(code|program|script)\b",
    ]

    _LOGIC_PATTERNS = [
        r"\b(explain|why\s+does|how\s+does|analyze|analyse|compare|architecture|pattern|design)\b",
        r"\b(step.{0,5}by.{0,5}step|in\s+detail|comprehensively|complex|reason)\b",
        r"\b(plan|summarize|evaluate|critique)\b",
    ]

    def generate_response_stream(self, text: str, history: list[dict] | None = None):
        """
        Yield LLM tokens as they arrive (streaming).

        Auto-selects the Ollama model based on query complexity when
        OLLAMA_AUTO_SELECT is enabled. Falls back to non-streaming if the
        backend does not implement generate_stream().

        Updates conversation memory after the full response is collected.
        """
        if not text or not text.strip():
            return

        conv_history = history if history is not None else self.memory.get_history()
        augmented_settings = self._get_augmented_settings()

        # Auto-select Ollama model for this request only
        original_model = augmented_settings.model
        if OLLAMA_AUTO_SELECT and augmented_settings.provider == "ollama":
            selected = self._select_model_for_query(text.strip())
            if selected != original_model:
                augmented_settings.model = selected
                logger.info("Auto-selected model: %s (was: %s)", selected, original_model)
                print(f"  [Auto-Select] Model: {selected}")

        backend = self._get_backend()
        full_response = ""

        try:
            for token in backend.generate_stream(augmented_settings, text.strip(), conv_history):
                full_response += token
                yield token
        except AttributeError:
            # Backend doesn't implement generate_stream — fall back
            logger.warning("Backend %s has no streaming support, falling back", augmented_settings.provider)
            response = backend.generate(augmented_settings, text.strip(), conv_history)
            full_response = response
            yield response
        except Exception as e:
            logger.error("Streaming error: %s", e, exc_info=True)
            yield f"Error: {e}"

        if full_response:
            self.memory.add("user", text.strip())
            self.memory.add("assistant", full_response)

    def generate_response(self, text: str, history: list[dict] | None = None) -> str:
        """
        Generate an LLM response with retry + optional failover.
        Stores conversation in memory for multi-turn context.
        """
        if not text or not text.strip():
            return ""

        # Use internal memory if no external history supplied
        conv_history = history if history is not None else self.memory.get_history()
        augmented_settings = self._get_augmented_settings()

        backend = self._get_backend()
        response = ""

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                t0 = time.time()
                response = backend.generate(augmented_settings, text.strip(), conv_history)
                elapsed = time.time() - t0

                logger.info(
                    "LLM response | provider=%s | model=%s | time=%.2fs | len=%d",
                    augmented_settings.provider, augmented_settings.model, elapsed, len(response),
                )

                # Store in memory
                self.memory.add("user", text.strip())
                self.memory.add("assistant", response)

                return response

            except requests.exceptions.ConnectionError:
                logger.warning("Connection failed (attempt %d/%d)", attempt, self.MAX_RETRIES)
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)  # exponential-ish backoff
                    continue
                # Try failover
                fallback = self._try_failover(text.strip(), conv_history)
                if fallback:
                    return fallback
                return f"Error: Could not connect to {augmented_settings.provider} LLM. Is it running?"

            except requests.exceptions.Timeout:
                logger.warning("Request timed out (attempt %d/%d)", attempt, self.MAX_RETRIES)
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return f"Error: {augmented_settings.provider} LLM timed out after {augmented_settings.timeout}s."

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                logger.error("HTTP error %d: %s", status, e)

                # Rate limit — retry with backoff
                if status == 429:
                    wait = min(self.RETRY_DELAY * (2 ** attempt), 15)
                    logger.warning("Rate limited (429), waiting %.1fs (attempt %d/%d)", wait, attempt, self.MAX_RETRIES)
                    if attempt < self.MAX_RETRIES:
                        time.sleep(wait)
                        continue
                    # Last resort: try failover to another provider
                    fallback = self._try_failover(text.strip(), conv_history)
                    if fallback:
                        return fallback
                    return f"Error: {augmented_settings.provider} rate limited. Try again in a minute or switch provider with 'llm provider groq'."

                # Auth error
                if status in (401, 403):
                    return f"Error: {augmented_settings.provider} API key is invalid or expired. Check your .env file."

                return f"Error: {augmented_settings.provider} returned HTTP {status}."

            except ValueError as e:
                logger.error("Value error: %s", e)
                return f"Error: {e}"

            except Exception as e:
                logger.error("Unexpected error: %s", e, exc_info=True)
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return f"Brain Error: {e}"

        return response or "Error: Failed to generate response."

    def _get_augmented_settings(self) -> BrainSettings:
        """
        Returns a copy of settings for this request.
        NOTE: Context injection is deliberately disabled — injecting OS/directory info
        into every prompt confuses small models and causes hallucinations.
        Context is only provided if explicitly requested by the user.
        """
        import copy
        return copy.copy(self.settings)

    def set_provider(self, provider_name: str) -> tuple[bool, str]:
        """Switch the active LLM provider."""
        provider_name = provider_name.strip().lower()
        try:
            provider = Provider(provider_name)
        except ValueError:
            valid = ", ".join(p.value for p in Provider)
            return False, f"Unknown provider '{provider_name}'. Valid: {valid}"

        # Validate API key for cloud providers
        key_map = {
            Provider.GEMINI: (GEMINI_API_KEY, "GEMINI_API_KEY"),
            Provider.GROQ:   (GROQ_API_KEY, "GROQ_API_KEY"),
            Provider.GROK:   (GROK_API_KEY, "GROK_API_KEY"),
        }
        if provider in key_map:
            api_key, env_name = key_map[provider]
            if not api_key:
                return False, f"Cannot switch to {provider.value}: {env_name} not set in .env"

        old_provider = self.settings.provider
        self.settings.provider = provider.value
        self.settings.model = self._default_model_for(provider.value)

        logger.info("Provider switched: %s → %s", old_provider, provider.value)
        return True, f"Provider switched to '{provider.value}' (model: {self.settings.model})."

    def set_model(self, model_name: str) -> tuple[bool, str]:
        model_name = (model_name or "").strip()
        if not model_name:
            return False, "Model name cannot be empty."
        self.settings.model = model_name
        return True, f"Model set to '{self.settings.model}' (provider: {self.settings.provider})."

    def set_option(self, option_name: str, raw_value: str) -> tuple[bool, str]:
        name = option_name.lower().strip()
        try:
            if name == "temperature":
                value = float(raw_value)
                if not self.settings.validate_temperature(value):
                    return False, "temperature must be between 0 and 2."
                self.settings.temperature = value
                return True, f"temperature set to {value}."

            if name == "top_p":
                value = float(raw_value)
                if not self.settings.validate_top_p(value):
                    return False, "top_p must be > 0 and <= 1."
                self.settings.top_p = value
                return True, f"top_p set to {value}."

            if name == "max_tokens":
                value = int(raw_value)
                if not self.settings.validate_max_tokens(value):
                    return False, "max_tokens must be a positive integer."
                self.settings.max_tokens = value
                return True, f"max_tokens set to {value}."

            if name == "timeout":
                value = int(raw_value)
                if not self.settings.validate_timeout(value):
                    return False, "timeout must be a positive integer (seconds)."
                self.settings.timeout = value
                return True, f"timeout set to {value}s."

            return False, f"Unknown option '{option_name}'. Valid: temperature, top_p, max_tokens, timeout."
        except ValueError:
            return False, f"Invalid value '{raw_value}' for {option_name}."

    def set_system_prompt(self, prompt: str) -> tuple[bool, str]:
        prompt = (prompt or "").strip()
        if not prompt:
            return False, "System prompt cannot be empty."
        self.settings.system_prompt = prompt
        return True, "System prompt updated."

    def set_persona(self, name: str) -> tuple[bool, str, str]:
        """Switch persona. Returns (ok, message, new_voice_id)."""
        ok, message = self.personas.set_active(name)
        if ok:
            profile = self.personas.get_active()
            self.settings.system_prompt = profile.system_prompt
            return True, message, profile.voice
        return False, message, ""

    def get_persona_name(self) -> str:
        """Return the active persona's display name."""
        return self.personas.get_active().display_name

    def reset_settings(self) -> str:
        self.personas.reset()
        active_persona = self.personas.get_active()
        self.settings = BrainSettings(
            provider=LLM_PROVIDER,
            model=self._default_model_for(LLM_PROVIDER),
            system_prompt=active_persona.system_prompt,
        )
        self.memory.clear()
        return "Brain settings, memory, and persona reset to defaults."

    def clear_memory(self) -> str:
        self.memory.clear()
        return "Conversation memory cleared."

    def get_status(self) -> dict:
        backend = self._get_backend()
        is_healthy = backend.health_check()
        return {
            "provider": self.settings.provider,
            "model": self.settings.model,
            "persona": self.personas.get_active().display_name,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "max_tokens": self.settings.max_tokens,
            "timeout": self.settings.timeout,
            "system_prompt_preview": self.settings.system_prompt[:120],
            "memory_messages": self.memory.length,
            "health": "connected" if is_healthy else "disconnected",
        }

    def list_local_models(self) -> tuple[bool, list[str] | str]:
        backend = self._get_backend()
        return backend.list_models()

    def execute_tool(self, tool_call: dict) -> str:
        """Placeholder for future tool/function-calling support."""
        logger.warning("execute_tool called but not yet implemented: %s", tool_call)
        return "Tool execution not yet implemented."

    # ── Private Helpers ─────────────────────────────────────────────────────

    def _get_backend(self):
        provider = Provider(self.settings.provider)
        return self._backends[provider]

    def _select_model_for_query(self, text: str) -> str:
        """Return the best Ollama model for the query: Fast, Logic, or Code."""
        # 1. Check for Code patterns
        for pat in self._CODE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                logger.debug("Auto-select: code query → %s", OLLAMA_CODE_MODEL)
                return OLLAMA_CODE_MODEL

        # 2. Check for Logic patterns
        for pat in self._LOGIC_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                logger.debug("Auto-select: logic query → %s", OLLAMA_LOGIC_MODEL)
                return OLLAMA_LOGIC_MODEL

        # 3. Check for length-based complexity
        if len(text.split()) > 25:
            return OLLAMA_LOGIC_MODEL

        # 4. Default to Fast model
        logger.debug("Auto-select: fast query → %s", OLLAMA_FAST_MODEL)
        return OLLAMA_FAST_MODEL

    def _default_model_for(self, provider: str) -> str:
        defaults = {
            "ollama": OLLAMA_MODEL,
            "gemini": GEMINI_MODEL,
            "groq":   GROQ_MODEL,
            "grok":   GROK_MODEL,
        }
        return defaults.get(provider, OLLAMA_MODEL)

    def _try_failover(self, text: str, history: list[dict]) -> Optional[str]:
        """Attempt to use another provider if the primary is down."""
        current = Provider(self.settings.provider)
        fallback_order = [p for p in Provider if p != current]

        for fallback_provider in fallback_order:
            backend = self._backends[fallback_provider]
            if backend.health_check():
                logger.info("Failing over to %s", fallback_provider.value)
                try:
                    # Temporarily use fallback settings
                    temp_settings = BrainSettings(
                        provider=fallback_provider.value,
                        model=self._default_model_for(fallback_provider.value),
                        temperature=self.settings.temperature,
                        top_p=self.settings.top_p,
                        max_tokens=self.settings.max_tokens,
                        timeout=self.settings.timeout,
                        system_prompt=self.settings.system_prompt,
                    )
                    response = backend.generate(temp_settings, text, history)
                    return f"[Failover → {fallback_provider.value}] {response}"
                except Exception as e:
                    logger.warning("Failover to %s failed: %s", fallback_provider.value, e)
                    continue

        return None
