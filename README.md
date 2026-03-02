<p align="center">
  <h1 align="center">🧠 Jarvis</h1>
  <p align="center">
    <strong>Autonomous Voice-Driven Coding Engine for Windows</strong>
  </p>
  <p align="center">
    Voice-controlled · Multi-LLM · Shell Execution · Persona System · Real-time TTS
  </p>
  <p align="center">
    <a href="#quickstart">Quickstart</a> •
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#local-llm-models">Models</a> •
    <a href="#persona-system">Personas</a> •
    <a href="#commands">Commands</a> •
    <a href="#roadmap">Roadmap</a>
  </p>
</p>

---

## What is Jarvis?

Jarvis is a **desktop AI assistant** that listens to your voice, understands natural language, executes system commands, and speaks back — all running natively on Windows with a PyQt6 interface.

Unlike chatbots that just *talk about* doing things, Jarvis **actually does them**. Say *"create a folder called Projects"* and it runs the PowerShell command. Ask *"what's running on port 3000?"* and it checks for you.

```
You:     "Hey Jarvis, list all Python files in Downloads"
Jarvis:  Here are your Python files.
         [EXEC] Get-ChildItem $env:USERPROFILE\Downloads -Filter *.py
         > script.py  main.py  utils.py
```

---

## Project Status

> **Last updated:** February 2026

### What's Built

| Module | File | Status | Description |
|---|---|---|---|
| **Core Brain** | `core/brain.py` | ✅ Complete | Multi-provider LLM (Ollama, Gemini, Groq, Grok) with retry, failover, and memory |
| **Orchestrator** | `core/orchestrator.py` | ✅ Complete | Command routing, shell execution, safety checks, meta-commands |
| **Persona System** | `core/personas.py` | ✅ **NEW** | 5 switchable personalities with matched voices |
| **Tools** | `core/tools.py` | ✅ Complete | Sandboxed file system operations |
| **TTS** | `output/tts.py` | ✅ Complete | Edge-TTS with dynamic voice switching per persona |
| **Listener** | `input/listener.py` | ✅ Complete | Wake word (Porcupine) + STT (Faster-Whisper) pipeline |
| **UI** | `ui/window.py` | ✅ Complete | PyQt6 GUI with thinking orb, terminal, command input panel |
| **Tray** | `ui/tray.py` | ✅ Complete | System tray with show/hide, pause/resume, quit |
| **Tests** | `tests/test_orchestrator.py` | ✅ 23 passing | Full coverage: commands, personas, voices, safety |

---

## Features

| Feature | Description |
|---|---|
| 🎙️ **Voice Interface** | Wake word detection ("Jarvis") via Porcupine + real-time speech-to-text via Faster-Whisper |
| 🧠 **Multi-LLM Brain** | Switch between **Groq**, **Gemini**, **Grok**, or local **Ollama** — at runtime |
| ⚡ **Shell Execution** | AI-generated PowerShell commands are auto-extracted and executed safely |
| 🔊 **Text-to-Speech** | Natural voice responses via Edge-TTS (Microsoft neural voices) |
| 🎭 **Persona System** | 5 built-in personalities (Witty, Professional, Friendly, Technical, Comic) with matched voices |
| 🛡️ **Safety Guards** | Dangerous commands (`format`, `rm -rf`, `diskpart`) are blocked automatically |
| 🔄 **Provider Failover** | If one LLM is down or rate-limited, Jarvis auto-switches to another |
| 💬 **Conversation Memory** | Sliding-window context (20 messages) for multi-turn conversations |
| 🎨 **Colored Terminal** | Semantic coloring — cyan for input, green for AI, yellow for commands, magenta for output |
| 🖥️ **Desktop UI** | PyQt6 window with embedded terminal, thinking orb, command input, and system tray |
| ⌨️ **Type or Talk** | Use the GUI command input bar *or* voice — both go through the same pipeline |
| 📦 **One-Click Launch** | `run_jarvis.bat` handles venv, dependencies, and env setup automatically |

---

## Local LLM Models

Jarvis uses **Ollama** for local-first LLM inference. All models are tested and working:

### Benchmarks (tested on local hardware)

| Model | Size | Response Time | Best For | Status |
|---|---|---|---|---|
| `gemma:2b` | 1.7 GB | **3.7s** | Default balance of speed and quality | ✅ Working |
| `gemma3:1b` | 815 MB | **2.5s** ⚡ | Quick interactions, simple tasks | ✅ Fastest |
| `llama3:latest` | 4.7 GB | **14.5s** | Complex reasoning, multi-step tasks | ✅ Working |
| `llama3.2:3b` | 2.0 GB | **20.3s** | Alternative mid-range model | ✅ Working |

> **Default:** `gemma:2b` — Best trade-off between speed and intelligence for everyday use.
>
> **Upgrade path:** When you need better code generation, pull `qwen2.5-coder:3b` via `ollama pull qwen2.5-coder:3b`.

### Switching Models at Runtime

```
llm use gemma3:1b           # Switch to fastest model
llm use llama3:latest       # Switch to smartest model
llm provider groq            # Switch to cloud (Groq) for max intelligence
```

---

## Persona System

Jarvis supports **switchable personality profiles** that bundle a personality style + TTS voice. Each persona modifies how Jarvis responds while preserving full functionality (command execution, shell tags, safety checks).

### Built-in Personas

| Persona | Key | Personality | Voice | Rate |
|---|---|---|---|---|
| 🎩 **Witty JARVIS** | `witty` | British sophistication, dry humor, addresses you as "sir" | `en-GB-RyanNeural` | +10% |
| 💼 **Professional** | `professional` | Concise, no-nonsense, zero fluff | `en-US-GuyNeural` | +15% |
| 😊 **Friendly** | `friendly` | Warm, encouraging, casual language | `en-US-JennyNeural` | +12% |
| 🔧 **Technical** | `technical` | Developer-focused, explains the "why", mentions edge cases | `en-US-AndrewNeural` | +8% |
| 🎬 **Comic Relief** | `comic` | Over-the-top dramatic narration, treats every task like a movie trailer | `en-AU-WilliamNeural` | +5% |

> **Default persona:** Witty JARVIS — because every AI assistant should have a bit of personality.

### Persona Examples

**Witty JARVIS** responding to "open notepad":
> *"Ah, Notepad. The pinnacle of text editing technology. Opening it now, sir."*

**Professional** responding to "open notepad":
> *"Opening Notepad."*

**Comic Relief** responding to "open notepad":
> *"AND SO IT BEGINS... the legendary Notepad shall be SUMMONED! *thunderclap*"*

### Persona Commands

```
persona list              — List all available personas with active marker
persona set witty         — Switch to Witty JARVIS (also changes voice)
persona set professional  — Switch to Professional mode
persona status            — Show active persona, voice, and style
persona reset             — Reset to default (witty)
```

### Voice Commands

```
voice list                — Show all recommended voices with descriptions
voice set en-GB-RyanNeural — Manually override TTS voice
voice status              — Show current voice
```

### Available Voices

| Voice ID | Description |
|---|---|
| `en-GB-RyanNeural` | British Male (witty default) |
| `en-US-GuyNeural` | American Male (professional) |
| `en-US-JennyNeural` | American Female (friendly) |
| `en-US-AndrewNeural` | American Male (technical) |
| `en-AU-WilliamNeural` | Australian Male (comic) |
| `en-GB-SoniaNeural` | British Female |
| `en-US-AriaNeural` | American Female |
| `en-IN-NeerjaNeural` | Indian Female |
| `en-IN-PrabhatNeural` | Indian Male |

---

## Quickstart

### Prerequisites

- **Python 3.10+** — [Download](https://python.org/downloads/)
- **Ollama** — [Download](https://ollama.com) (for local LLM) — *recommended for getting started*
- **API Key** (optional, for cloud providers):
  - [Groq](https://console.groq.com/keys) (free, fastest cloud option)
  - [Gemini](https://aistudio.google.com/apikey) (free tier available)

### Setup (4 steps)

```powershell
# 1. Clone and enter the project
git clone https://github.com/your-username/Antigravity.git
cd Antigravity

# 2. Create virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r Jarvis\requirements.txt

# 3. Install a local model via Ollama
ollama pull gemma:2b

# 4. Configure your environment
copy .env.example .env
notepad .env          # Set LLM_PROVIDER=ollama (default)
```

### Run

```powershell
.\run_jarvis.bat
```

Or manually:
```powershell
.venv\Scripts\activate
python -m Jarvis.main
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      Jarvis App                          │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐   │
│  │ Listener │───▶│ Orchestrator │───▶│    Brain      │   │
│  │ (Voice)  │    │  (Router)    │◀───│ (Multi-LLM)   │   │
│  └──────────┘    │              │    │               │   │
│       │          │  ┌────────┐  │    │ ┌───────────┐ │   │
│       │          │  │ Tools  │  │    │ │  Persona  │ │   │
│       │          │  └────────┘  │    │ │  Manager  │ │   │
│       │          │  ┌────────┐  │    │ └───────────┘ │   │
│       │          │  │ Shell  │  │    └───────────────┘   │
│       │          │  └────────┘  │     ▲  ▲  ▲  ▲        │
│       ▼          └──────┬───────┘     │  │  │  │         │
│  ┌──────────┐           │             │  │  │  └ Ollama  │
│  │  STT     │    ┌──────▼───────┐     │  │  └── Grok    │
│  │(Whisper) │    │     TTS      │     │  └───── Gemini  │
│  └──────────┘    │  (Edge-TTS)  │     └──────── Groq    │
│                  │  per-persona │                        │
│                  └──────────────┘                        │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │      PyQt6 UI (Window + Tray + Command Input)    │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### How It Works — The "Speak-to-Shell" Pipeline

```
  🎤 LISTEN          🧠 THINK           ⚡ ACT             🔊 RESPOND
┌───────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Wake Word │───▶│ Orchestrator │───▶│   Execute    │───▶│   Edge-TTS   │
│ + Whisper │    │ classifies:  │    │  PowerShell  │    │  speaks back │
│  STT      │    │ Shell? LLM?  │    │  command     │    │  to user     │
└───────────┘    │ Meta-cmd?    │    └──────────────┘    └──────────────┘
                 └──────────────┘
```

1. **Listen** — Porcupine detects "Jarvis" wake word → audio captured → Faster-Whisper transcribes to text
2. **Think** — Orchestrator classifies intent:
   - Direct shell command? → Execute immediately
   - Meta-command (`llm status`, `persona set`)? → Handle internally
   - Natural language? → Send to Brain (LLM) with active persona's system prompt
3. **Act** — LLM response parsed for `[SHELL]...[/SHELL]` tags → safety-checked → executed in PowerShell
4. **Respond** — Text response spoken via Edge-TTS using the active persona's voice

### Project Structure

```
Antigravity/
├── run_jarvis.bat              # One-click launcher
├── .env                        # API keys & config (git-ignored)
├── .env.example                # Reference config template
│
└── Jarvis/
    ├── main.py                 # App entry point — wires everything together
    ├── config.py               # Environment loading & constants
    ├── requirements.txt        # Python dependencies
    │
    ├── core/
    │   ├── brain.py            # Multi-provider LLM interface (Groq/Gemini/Grok/Ollama)
    │   ├── orchestrator.py     # Command router & shell executor
    │   ├── personas.py         # 🆕 Persona profiles & manager
    │   ├── tools.py            # Sandboxed file system operations
    │   └── colors.py           # Terminal color utilities
    │
    ├── input/
    │   ├── listener.py         # Autonomous voice listener (wake word + recording)
    │   ├── audio_capture.py    # Microphone audio capture
    │   └── transcribe_worker.py # Faster-Whisper STT worker thread
    │
    ├── output/
    │   ├── tts.py              # Edge-TTS text-to-speech (dynamic voice switching)
    │   └── visuals.py          # Thinking orb animation
    │
    ├── ui/
    │   ├── window.py           # Main PyQt6 window with command input panel
    │   └── tray.py             # System tray icon & menu
    │
    └── tests/
        └── test_orchestrator.py # 19 unit tests (commands, personas, voices, safety)
```

---

## Configuration

All configuration is done via the `.env` file in the project root:

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | Active LLM backend | `ollama` |
| `OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434/api/generate` |
| `OLLAMA_MODEL` | Default Ollama model | `gemma:2b` |
| `GROQ_API_KEY` | Groq Cloud API key | — |
| `GROQ_MODEL` | Groq model name | `llama-3.3-70b-versatile` |
| `GEMINI_API_KEY` | Google Gemini API key | — |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.0-flash` |
| `GROK_API_KEY` | xAI Grok API key | — |
| `GROK_MODEL` | Grok model name | `grok-3-mini-fast` |
| `PORCUPINE_ACCESS_KEY` | Picovoice wake word key | — |
| `TTS_VOICE` | Default Edge-TTS voice (overridden by persona) | `en-US-GuyNeural` |
| `DEFAULT_PERSONA` | Starting persona on launch | `witty` |

### Provider Comparison

| Provider | Speed | Intelligence | Cost | Needs Internet | Best For |
|---|---|---|---|---|---|
| **Ollama** | Varies by model | Depends on model | Free | ❌ No | Privacy, offline use |
| **Groq** | ⚡ Fastest cloud | 🧠🧠🧠 (Llama 3.3 70B) | Free tier | ✅ Yes | Maximum speed |
| **Gemini** | Fast | 🧠🧠🧠 (Flash) | Free tier | ✅ Yes | Google ecosystem |
| **Grok** | Fast | 🧠🧠🧠 (xAI) | Paid | ✅ Yes | xAI users |

---

## Commands

### Voice Commands
Just say **"Jarvis"** followed by your request:
- *"Jarvis, what time is it?"*
- *"Jarvis, open notepad"*
- *"Jarvis, list files in my Downloads"*
- *"Jarvis, create a folder called Projects"*
- *"Jarvis, how much RAM am I using?"*

### Brain Control Commands

| Command | Description |
|---|---|
| `llm status` | Show provider, model, persona, and health |
| `llm models` | List available models for current provider |
| `llm provider <name>` | Switch provider (`groq`/`gemini`/`grok`/`ollama`) |
| `llm use <model>` | Switch model (e.g., `llm use gemma3:1b`) |
| `llm set temperature <0..2>` | Adjust creativity |
| `llm set max_tokens <int>` | Set response length limit |
| `llm set timeout <seconds>` | Set request timeout |
| `llm prompt show` | View active system prompt |
| `llm prompt set <text>` | Override system prompt |
| `llm reset` | Reset all settings, memory, and persona to defaults |
| `clear memory` | Clear conversation history |

### Persona Commands

| Command | Description |
|---|---|
| `persona list` | List all personas with active indicator |
| `persona set <name>` | Switch persona + auto-update voice |
| `persona status` | Show active persona, voice, and style |
| `persona reset` | Reset to default (Witty JARVIS) |

### Voice Commands

| Command | Description |
|---|---|
| `voice list` | Show all recommended Edge-TTS voices |
| `voice set <voice_id>` | Manually set TTS voice |
| `voice status` | Show current voice |

### Direct Shell Commands
These bypass the LLM and execute directly:

```
dir                           — List directory contents
git status                    — Check git status
pip list                      — List Python packages
ipconfig                      — Show network config
tasklist                      — List running processes
python script.py              — Run a Python script
```

---

## Safety

Jarvis includes safety guards for commands generated by the LLM:

| Blocked Pattern | Risk |
|---|---|
| `format c:` | Drive formatting |
| `rm -rf` / `Remove-Item -Recurse` | Recursive deletion |
| `diskpart` | Disk partitioning |
| `bcdedit` | Boot config modification |
| `reg delete` | Registry deletion |
| `shutdown` / `restart` | System shutdown |

If a dangerous command is detected in the LLM's response, Jarvis **blocks it** and shows a warning instead of executing.

---

## Terminal Color Scheme

| Color | Meaning | Tag |
|---|---|---|
| 🔵 **Bright Cyan** | Your input (voice/typed) | `[YOU]` |
| 🟢 **Bright Green** | AI responses | `[JARVIS]` |
| 🟡 **Bright Yellow** | Shell commands being executed | `[EXEC]` |
| 🟣 **Magenta** | Shell command output | *(raw output)* |
| 🔴 **Bright Red** | Errors | `[ERROR]` |
| 🔵 **Bright Blue** | System info | `[INFO]` |
| ⚪ **Dark Gray** | Debug/timing info | *(dimmed)* |

---

## Development

### Running Tests
```powershell
# Run all 19 tests
.venv\Scripts\python.exe -m unittest Jarvis.tests.test_orchestrator -v
```

### Testing the Brain Directly
```python
from Jarvis.core.brain import Brain
brain = Brain()
response = brain.generate_response("Hello, what can you do?")
print(response)
```

### Testing Personas Programmatically
```python
from Jarvis.core.personas import PersonaManager
pm = PersonaManager()
pm.set_active("comic")
profile = pm.get_active()
print(f"Active: {profile.display_name} | Voice: {profile.voice}")
```

### Switching Providers Programmatically
```python
from Jarvis.core.brain import Brain
brain = Brain(provider="groq")       # Start with Groq
brain.set_provider("gemini")          # Switch to Gemini
brain.set_model("gemini-2.0-flash")   # Change model
brain.set_persona("professional")     # Switch persona
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Desktop UI | PyQt6 |
| Wake Word | Porcupine (Picovoice) |
| Speech-to-Text | Faster-Whisper (local) |
| Text-to-Speech | Edge-TTS (Microsoft Neural) |
| LLM Providers | Ollama · Groq · Gemini · Grok |
| Local Models | gemma:2b · gemma3:1b · llama3 · llama3.2:3b |
| Persona System | 5 built-in profiles with auto-linked voices |
| Shell | PowerShell (Windows native) |
| Config | python-dotenv |

---

## Roadmap

### Phase 1: Stability & Polish *(Immediate)*

| Feature | Description | Status |
|---|---|---|
| **Feedback Loop** | Feed shell output back to LLM for verification/debugging | ✅ Done |
| **Error Auto-Recovery** | LLM auto-suggests fixes when commands fail | ✅ Done |
| **Task-Aware Context** | Conversation memory that remembers project context | ✅ Done |

### Phase 2: Better Models & Performance

| Feature | Description | Status |
|---|---|---|
| Model Auto-Selection | Route simple tasks to `gemma3:1b`, complex to `llama3` | ✅ Done |
| Streaming Responses | Token-by-token display for faster perceived speed | ✅ Done |
| Qwen3-Coder Support | Pull and integrate `qwen2.5-coder:3b` for code tasks | ✅ Done |

### Phase 3: Safety & Sandboxing

| Feature | Description | Status |
|---|---|---|
| **Confirmation Mode** | User-in-the-loop approval before executing LLM commands | ✅ Done |
| **WSL Sandbox** | Route risky commands to Windows Subsystem for Linux | ✅ Done |
| **Command Audit Log** | Log every executed command with timestamps | 🔲 Planned |

### Phase 4: Advanced Features

| Feature | Description | Status |
|---|---|---|
| Multi-file Editing | LLM generates code across multiple files | 🔲 Planned |
| Web UI | Browser-based interface alongside desktop app | 🔲 Planned |
| Plugin System | User-defined tools/commands the LLM can invoke | 🔲 Planned |
| Cross-platform | macOS / Linux support | 🔲 Planned |
| Conversation Persistence | Save/load conversation sessions | 🔲 Planned |

---

## License

This project is proprietary. All rights reserved.

---

<p align="center">
  Built with focus and intention.
</p>
