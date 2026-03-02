# Plan: Jarvis Full Repair & Hardening

**TL;DR**: The fine-tuned `jarvis-action` model is broken (repetitive loops, no instruction following). The fix is two-fold: (A) create a proper Ollama model from `qwen2.5:1.5b-instruct` with a Jarvis system prompt + correct parameters, and (B) fix all bugs discovered in the codebase — dead config, broken tests, tag format mismatches, missing dependencies, and a fragile export pipeline. The work is split into two independent parts that can run in parallel.

---

## Part 1 — VS Code Copilot (You & Me)
*Focus: Runtime fixes, config cleanup, Ollama model setup, test repair*

### Step 1: Fix the Ollama model — replace broken fine-tune with prompted instruct model
- Create `Modelfile.jarvis` with `FROM qwen2.5:1.5b-instruct` (not a broken GGUF), using the **colon tag format** (matching `parse_action_tag()`) — not JSON format
- Set `PARAMETER repeat_penalty 1.3` to prevent the repetition loop
- The SYSTEM prompt in the Modelfile is a **backup only** — `brain.py` overrides it with `settings.system_prompt` via the `"system"` field in every API call
- Remove `stop` parameters for `[/SHELL]` and `[/ACTION]` — these were stripping tags before the orchestrator could parse them
- Run: `ollama pull qwen2.5:1.5b-instruct` then `ollama create jarvis-action -f Modelfile.jarvis`
- Smoke test: `ollama run jarvis-action "open notepad"`

### Step 2: Clean up `.env`
- Remove duplicate `OLLAMA_MODEL=jarvis-action` on line 27
- Remove dead `JARVIS_MODEL=jarvis-action` (never read by any code)
- Keep `OLLAMA_MODEL=jarvis-action`, `OLLAMA_FAST_MODEL=jarvis-action`

### Step 3: Reinstall CUDA PyTorch
- `pip uninstall torch torchvision torchaudio -y`
- `pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121`
- Verify: `python -c "import torch; print(torch.cuda.is_available())"` → `True`

### Step 4: Fix broken tests
- `tests/test_terminal_interaction.py` — imports non-existent `Jarvis.ui.terminal`. Either delete or rewrite to use `MainWindow.command_submitted`
- `tests/test_ui_launch.py` (line 25) — asserts `"Jarvis Hybrid Brain"` but window title is `"Jarvis AI"`. Fix assertion
- `test_minimal.py` (line 48) — references `window.terminal.command_signal`. Fix to use `window.command_submitted`

### Step 5: Fix `requirements.txt` — add missing `psutil`
- `windows.py` imports `psutil` in `get_system_info()` but it's not in `requirements.txt`
- Add `psutil>=5.9.0` to requirements

### Step 6: Fix Modelfile ACTION tag format mismatch
- The current `export_to_ollama.py` generates a SYSTEM prompt with JSON-format tags: `[ACTION]{"type": "open_app", "target": "app_name"}[/ACTION]`
- The runtime parser `parse_action_tag()` in `action_router.py` expects colon format: `[ACTION]launch_app: notepad[/ACTION]`
- Fix the export script's generated SYSTEM prompt to use colon format
- Fix the `export_to_ollama.py` to hint `OLLAMA_MODEL` not `JARVIS_MODEL`

### Step 7: Integration test
- Run `.\run_jarvis.bat` and verify:
  - "open notepad" → produces `[ACTION]launch_app: notepad[/ACTION]` → notepad opens
  - "tell me a joke" → natural text, no tags
  - "shutdown my PC" → warning message, no tags until confirmed

---

## Part 2 — Google Antigravity IDE
*Focus: SFT pipeline repair, dataset rebalancing, safety hardening, export pipeline*

### Step 1: Rebalance the SFT dataset
- Current distribution in `generate_dataset.py`: 49.7% `app_launch` — way too skewed
- Target distribution: max 20% per category — `app_launch` 18%, `url_open` 12%, `shell_safe` 18%, `shell_dangerous` 15%, `shell_critical` 7%, `conversational` 18%, `system_info` 5%, `mixed` 4%, `multi_action` 3%
- Add more conversational examples to `seed_dataset.jsonl` — greetings, recipes, jokes, weather, math, coding questions, trivia, etc.
- Rerun generation: `python -m Jarvis.sft.generate_dataset`

### Step 2: Fix training to use instruct base model
- Update `train_qlora.py` default `--model` from `Qwen/Qwen2.5-1.5B` to `Qwen/Qwen2.5-1.5B-Instruct`
- The instruct model already understands chat format + following instructions — LoRA only needs to teach the Jarvis tag vocabulary

### Step 3: Fix the export pipeline
- `export_to_ollama.py`: The `convert_to_gguf()` function runs `pip install -r llama.cpp/requirements.txt` which **replaces CUDA PyTorch with CPU-only** — this has happened twice already
- Fix: filter out `torch` from llama.cpp's requirements before installing, or pin the CUDA index URL
- Fix: change `--outtype q4_k_m` / `q8_0` to `f16` (avoid quantization quality loss on 1.5B models)
- Fix: SYSTEM prompt in generated Modelfile uses JSON format tags — must match colon format
- Fix: print hint should say `OLLAMA_MODEL` not `JARVIS_MODEL`

### Step 4: Safety layer hardening
- Review `SafetyEngine` risk patterns for completeness:
  - Add patterns for: `wsl`, `powershell -ep bypass`, `certutil`, `bitsadmin`, `mshta`, `wmic`, `cscript`, `wscript` (Windows LOLBins)
  - Add patterns for: `Invoke-WebRequest` + pipe to `iex`, encoded PowerShell commands (`-enc`, `-EncodedCommand`)
- Add rate limiting to shell execution — prevent rapid-fire command flooding
- Add audit logging persistence (write to `Jarvis/logs/` instead of in-memory only)

### Step 5: Clean up dead code
- Delete `audio_capture.py` — 40-line unused stub
- Remove `pvporcupine` from `requirements.txt` — imported but never used
- Delete or convert `web_view.py` — 7-line stub loading google.com

### Step 6: Add guardrails for SFT models in the orchestrator
- In `orchestrator.py` `_process_with_llm()`, add a **repetition detector**: if the LLM output contains the same line repeated 3+ times, truncate and return an error message like "Model produced repetitive output — falling back to conversational mode"
- This prevents the exact failure mode seen with the broken `jarvis-action` model

### Step 7: Run full test suite + validation
- `python -m pytest Jarvis/tests/ -v` — all tests must pass
- `python -m Jarvis.sft.schema --validate Jarvis/sft/seed_dataset.jsonl`
- `python -m Jarvis.sft.eval_structured` — offline metrics baseline

---

## Verification Matrix

| Check | Command | Expected |
|-------|---------|----------|
| Ollama model works | `ollama run jarvis-action "open notepad"` | `[ACTION]launch_app: notepad[/ACTION]` |
| No repetition | `ollama run jarvis-action "what time is it"` | Short response with `[SHELL]Get-Date...[/SHELL]` |
| CUDA enabled | `python -c "import torch; print(torch.cuda.is_available())"` | `True` |
| Tests pass | `python -m pytest Jarvis/tests/ -v` | All green |
| Safety blocks critical | In-app: "format C drive" | Blocked by safety gate |
| Jarvis runs | `.\run_jarvis.bat` | UI launches, voice works |

---

## Key Decisions

- **Chose prompted instruct model over broken fine-tune**: The LoRA-merged GGUF produces garbage. A properly prompted `qwen2.5:1.5b-instruct` with `repeat_penalty 1.3` works immediately and reliably.
- **Kept SFT pipeline for future use**: The training infrastructure is sound; only the dataset balance and export were broken. Part 2 fixes both for a future re-attempt.
- **Colon format over JSON format**: The runtime parser (`parse_action_tag()`) expects `launch_app: notepad`, not `{"type": "open_app"}`. All prompts and Modelfiles must match this.
- **No stop tokens in Modelfile**: Stop tokens `[/SHELL]` and `[/ACTION]` cause Ollama to strip the closing tags, which breaks the orchestrator's regex parser. The `brain.py` system prompt + `num_predict` limit handles output length instead.
