# Jarvis — Developer Documentation

> Internal module reference for contributors and developers.
> For user-facing documentation, see the [root README](../README.md).

---

## Module Overview

### `core/` — Intelligence Layer

| File | Class | Purpose |
|---|---|---|
| `brain.py` | `Brain` | Multi-provider LLM interface. Manages conversation memory, retries, failover, and settings. Supports Groq, Gemini, Grok, and Ollama backends. Integrates with `PersonaManager` for persona-aware system prompts. |
| `orchestrator.py` | `Orchestrator` | Command router. Classifies user input into shell commands, meta-commands, persona/voice commands, or LLM queries. Handles `[SHELL]` tag extraction and safe execution. |
| `personas.py` | `PersonaManager` | Persona profile system. Defines `PersonaProfile` dataclass and 5 built-in personas (witty, professional, friendly, technical, comic). Manages active persona switching and custom registration. |
| `tools.py` | `Tools` | Sandboxed file system operations. All paths are restricted to the `workspace/` directory. |
| `colors.py` | *(functions)* | ANSI terminal color utilities. Semantic coloring for user input, AI responses, shell commands, errors, etc. Uses `colorama` for Windows support. |

### `input/` — Voice Pipeline

| File | Class | Purpose |
|---|---|---|
| `listener.py` | `Listener` | Autonomous voice listener. Manages Porcupine wake word detection → audio recording → STT transcription pipeline. Emits `command_received` signal. |
| `audio_capture.py` | — | Raw microphone capture using `sounddevice`. Returns numpy audio arrays. |
| `transcribe_worker.py` | `TranscribeWorker` | Background thread running Faster-Whisper for speech-to-text. Persistent model loading for fast inference. |

### `output/` — Response Pipeline

| File | Class | Purpose |
|---|---|---|
| `tts.py` | `TTS` | Text-to-speech via Edge-TTS. Supports dynamic voice and rate switching per persona. Generates MP3 audio files and emits `audio_generated` signal for playback. |
| `visuals.py` | `ThinkingOrb` | Animated circular widget showing system state (idle, listening, thinking, speaking). |

### `ui/` — Desktop Interface

| File | Class | Purpose |
|---|---|---|
| `window.py` | `MainWindow` | Main PyQt6 window with embedded terminal, thinking orb, and audio player. |
| `tray.py` | `JarvisTrayIcon` | System tray icon with show/hide, pause/resume, and quit controls. |

### Root Files

| File | Purpose |
|---|---|
| `main.py` | Application entry point. Wires Orchestrator, TTS, Listener, UI, and Tray together. Passes TTS instance to Orchestrator for persona-driven voice switching. |
| `config.py` | Environment variable loading via `python-dotenv`. Defines all configurable constants (API keys, model names, paths, `DEFAULT_PERSONA`). |

---

## Data Flow

```
                  ┌─────────────┐
                  │  Porcupine  │  ← Wake word "Jarvis"
                  └──────┬──────┘
                         ▼
                  ┌─────────────┐
                  │  Recording  │  ← sounddevice captures audio
                  └──────┬──────┘
                         ▼
                  ┌─────────────┐
                  │   Whisper   │  ← Faster-Whisper transcribes
                  └──────┬──────┘
                         ▼
              ┌──────────────────┐
              │   Orchestrator   │  ← Classifies intent
              │                  │
              │  ┌─ Shell? ──────┼──▶ subprocess.run(powershell)
              │  │               │
              │  ├─ Meta-cmd? ───┼──▶ Brain.set_*() / get_status()
              │  │               │
              │  └─ Natural? ────┼──▶ Brain.generate_response()
              │                  │         │
              │  [SHELL] parse ◀─┼─────────┘
              │  Safety check    │
              │  Execute if safe │
              └───────┬──────────┘
                      ▼
              ┌──────────────┐
              │   Edge-TTS   │  ← Generate speech audio
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │  QMediaPlayer│  ← Play audio through speakers
              └──────────────┘
```

---

## Brain Provider Architecture

Each LLM provider implements the same interface:

```python
class _Backend:
    def generate(settings, prompt, history) -> str: ...
    def health_check() -> bool: ...
    def list_models() -> tuple[bool, list[str] | str]: ...
```

The `Brain` class:
- Holds a `BrainSettings` dataclass and `ConversationMemory`
- Routes `generate_response()` calls to the active backend
- Implements retry logic (3 attempts with exponential backoff)
- Auto-fails over to another healthy provider on connection failure or rate limiting (429)
- Stores conversation in a sliding-window buffer (last 20 messages)

### Adding a New Provider

1. Create a new `_NewProviderBackend` class in `brain.py`
2. Add the provider to the `Provider` enum
3. Add config constants to `config.py`
4. Register the backend in `Brain.__init__()._backends`
5. Add the default model to `Brain._default_model_for()`

---

## Signal Flow (Qt)

```
Listener.command_received  ──▶  main.on_command_input()
                                    │
                                    ├──▶  Orchestrator.process_command()
                                    │
                                    ├──▶  Worker.output_ready  ──▶  MainWindow.append_terminal_output()
                                    │
                                    └──▶  TTS.speak()
                                              │
                                              └──▶  TTS.audio_generated  ──▶  MainWindow.play_audio()

Listener.state_changed  ──▶  MainWindow.orb.set_state()
                         ──▶  MainWindow.update_status()
                         ──▶  JarvisTrayIcon.update_icon()
```

All cross-thread signals use `Qt.ConnectionType.QueuedConnection` for thread safety.

---

## Testing

```powershell
# Run all orchestrator tests
.venv\Scripts\python.exe -m unittest Jarvis.tests.test_orchestrator -v

# Quick smoke test
.venv\Scripts\python.exe -c "from Jarvis.core.brain import Brain; b = Brain(); print(b.generate_response('Hello'))"
```

Tests use `unittest.mock.patch` to avoid real API calls. The Brain and PersonaManager are fully mocked in `TestOrchestrator.setUp()`. Tests cover:
- Command routing (shell vs LLM)
- Meta-commands (`llm status`, `llm use`, etc.)
- Persona commands (`persona list`, `persona set`, etc.)
- Voice commands (`voice set`, `voice list`)
- Safety checks (dangerous command blocking)

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **REST API calls instead of SDKs** | Avoids heavy SDK dependencies. All providers use simple `requests.post()` calls. |
| **No async/await** | Keeps the codebase simple. Background threads via `threading.Thread` are sufficient for the current use case. |
| **Sliding-window memory** | Fixed-size buffer prevents unbounded memory growth. 20 messages is enough for conversational context. |
| **[SHELL] tag protocol** | Simple, parseable format that works with any LLM. No function-calling API dependency. |
| **Colorama over termcolor** | Better Windows terminal support. `colorama.init(autoreset=True)` handles ANSI on legacy cmd.exe. |
| **Safety blocklist** | Regex-based blocking is fast and transparent. Easy to extend without touching LLM prompts. |
