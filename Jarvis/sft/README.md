# Gemma 2B SFT Fine-Tuning for Jarvis Action Reliability

This directory contains everything needed to supervised-fine-tune (SFT) a
Gemma 2B model to reliably produce structured `[ACTION]` and `[SHELL]` tags
that Jarvis's runtime can parse and execute.

## Directory Layout

```
sft/
├── README.md               ← You are here
├── schema.py               ← JSONL schema + validation
├── seed_dataset.jsonl       ← 40-example seed dataset
├── generate_dataset.py      ← Expand seed → full training set via templates
├── train_qlora.py           ← QLoRA fine-tuning script (Gemma 2B)
├── eval_structured.py       ← Offline eval: tag validity, intent accuracy
└── convert_to_chat.py       ← Convert JSONL → chat-format for training
```

## Quick Start

1. **Validate seed data**: `python -m Jarvis.sft.schema --validate sft/seed_dataset.jsonl`
2. **Expand dataset**: `python -m Jarvis.sft.generate_dataset --out sft/train.jsonl --count 500`
3. **Train**: `python -m Jarvis.sft.train_qlora --data sft/train.jsonl --model google/gemma-2b`
4. **Evaluate**: `python -m Jarvis.sft.eval_structured --data sft/test.jsonl --model ./output`

## Dataset Format

Each line in the JSONL is a training example with:

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique example ID |
| `split` | str | train/val/test |
| `scenario` | str | Category (app_launch, shell_safe, shell_dangerous, conversational, ...) |
| `user_input` | str | What the user says |
| `assistant_text` | str | Conversational text outside tags |
| `action_tags` | list[str] | Expected `[ACTION]` tag contents |
| `shell_tags` | list[str] | Expected `[SHELL]` tag contents |
| `risk_level` | str | low/medium/high/critical |
| `requires_confirmation` | bool | Should model ask before executing? |
| `should_block` | bool | Should runtime block this entirely? |
| `expected_outcome` | str | executed/confirmed/denied/blocked/conversational |

## Safety-Aligned Training

The model is trained to:
- **Never** emit executable tags for CRITICAL operations
- **Always** warn and ask confirmation for HIGH-risk operations
- Execute LOW/MEDIUM operations immediately with appropriate tags
- Respond conversationally (no tags) for non-actionable queries
