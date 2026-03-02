"""Persistent transcription worker — stays alive, model loaded in memory.
Reads WAV file paths from stdin, writes JSON results to stdout.

Supports multi-language transcription:
  - Default: auto-detect language (works with Hindi, English, etc.)
  - Send "LANG:hi" to force Hindi, "LANG:en" for English, "LANG:auto" to auto-detect
"""
import sys
import os
import json
import time

def main():
    # Load model ONCE at startup
    t0 = time.time()
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print(json.dumps({"status": "ready", "load_time": round(time.time() - t0, 2)}), flush=True)

    # Language setting: None = auto-detect (default)
    # Can be overridden via STT_LANGUAGE env var or LANG: command
    lang = os.environ.get("STT_LANGUAGE", "auto")
    if lang.lower() == "auto":
        lang = None  # Whisper auto-detects

    # Process loop — read WAV paths or commands from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "EXIT":
            break

        # Handle language switching command: "LANG:hi", "LANG:en", "LANG:auto"
        if line.startswith("LANG:"):
            new_lang = line[5:].strip().lower()
            if new_lang == "auto":
                lang = None
                print(json.dumps({"status": "lang_set", "language": "auto"}), flush=True)
            else:
                lang = new_lang
                print(json.dumps({"status": "lang_set", "language": lang}), flush=True)
            continue

        wav_path = line
        try:
            t1 = time.time()
            segments, info = model.transcribe(
                wav_path,
                beam_size=1,
                language=lang,  # None = auto-detect, "en" = English, "hi" = Hindi, etc.
                initial_prompt="Jarvis open browser terminal script create folder file help status stop minimize quit spotify instagram chrome youtube netflix whatsapp",
            )
            segments_list = list(segments)
            text = " ".join([s.text for s in segments_list]).strip()
            elapsed = round(time.time() - t1, 2)

            result = {
                "text": text,
                "error": None,
                "time": elapsed,
                "language": info.language if lang is None else lang,
            }
            print(json.dumps(result), flush=True)
        except Exception as e:
            print(json.dumps({"text": "", "error": str(e), "time": 0}), flush=True)

if __name__ == "__main__":
    main()

