"""
Chat Format Converter — JSONL → Chat Messages for Training
=============================================================
Converts the SFT dataset into chat-formatted JSONL suitable for
fine-tuning with transformers / trl / unsloth.

Usage:
    python -m Jarvis.sft.convert_to_chat --input sft/train.jsonl --output sft/train_chat.jsonl
"""

import json
import argparse
from pathlib import Path

# Minimal system prompt for training (keeps token count low for 2B model)
TRAINING_SYSTEM_PROMPT = (
    "You are Jarvis, an AI assistant on Windows. "
    "Execute tasks using [ACTION] or [SHELL] tags. "
    "Use [ACTION]launch_app: name[/ACTION] for apps, "
    "[ACTION]open_url: url[/ACTION] for websites, "
    "[SHELL]command[/SHELL] for PowerShell commands. "
    "For destructive commands (delete, format, shutdown, registry), "
    "warn the user and ask confirmation first — do NOT emit tags until confirmed. "
    "For conversational queries, respond naturally without tags."
)


def example_to_chat(data: dict, system_prompt: str) -> dict:
    """
    Convert one JSONL example to chat-message format.

    Output format:
        {"messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]}
    """
    # Build the target assistant output
    parts = []
    if data.get("assistant_text"):
        parts.append(data["assistant_text"])
    for tag in data.get("action_tags", []):
        parts.append(f"[ACTION]{tag}[/ACTION]")
    for tag in data.get("shell_tags", []):
        parts.append(f"[SHELL]{tag}[/SHELL]")

    assistant_content = "\n".join(parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": data["user_input"]},
        {"role": "assistant", "content": assistant_content},
    ]

    return {"messages": messages}


def convert_file(input_path: str, output_path: str, system_prompt: str) -> int:
    """Convert an entire JSONL file to chat format."""
    count = 0
    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            chat = example_to_chat(data, system_prompt)
            fout.write(json.dumps(chat, ensure_ascii=False) + "\n")
            count += 1

    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert JSONL to chat format")
    parser.add_argument("--input", required=True, help="Input JSONL path")
    parser.add_argument("--output", required=True, help="Output chat JSONL path")
    parser.add_argument("--system-prompt", default=TRAINING_SYSTEM_PROMPT,
                        help="System prompt to inject")
    args = parser.parse_args()

    count = convert_file(args.input, args.output, args.system_prompt)
    print(f"Converted {count} examples -> {args.output}")
