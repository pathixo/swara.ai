"""
SFT Dataset Schema — Validation & Types
==========================================
Defines the JSONL schema for Gemma 2B fine-tuning data and provides
validation utilities for quality control before training.
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Scenario(str, Enum):
    """Training example categories."""
    APP_LAUNCH      = "app_launch"
    URL_OPEN        = "url_open"
    SHELL_SAFE      = "shell_safe"
    SHELL_DANGEROUS = "shell_dangerous"
    SHELL_CRITICAL  = "shell_critical"
    SYSTEM_INFO     = "system_info"
    CONVERSATIONAL  = "conversational"
    MIXED           = "mixed"              # conversation + action
    MALFORMED       = "malformed_recovery" # model should NOT output broken tags
    MULTI_ACTION    = "multi_action"       # multiple tags in one response


class RiskLabel(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class ExpectedOutcome(str, Enum):
    EXECUTED       = "executed"        # safe, runs immediately
    CONFIRMED      = "confirmed"       # asks confirmation, user approves
    DENIED         = "denied"          # asks confirmation, user denies
    BLOCKED        = "blocked"         # runtime blocks (CRITICAL)
    CONVERSATIONAL = "conversational"  # no executable tags emitted


@dataclass
class SFTExample:
    """One training example for structured action fine-tuning."""
    id: str
    split: str                              # train / val / test
    scenario: str                           # Scenario enum value
    user_input: str                         # Raw user utterance
    assistant_text: str                     # Conversational response text
    action_tags: list[str] = field(default_factory=list)   # ACTION tag contents
    shell_tags: list[str] = field(default_factory=list)    # SHELL tag contents
    risk_level: str = "low"                 # RiskLabel enum value
    requires_confirmation: bool = False
    should_block: bool = False
    expected_outcome: str = "executed"      # ExpectedOutcome enum value

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "SFTExample":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def format_assistant_output(self) -> str:
        """
        Reconstruct the full assistant output as the model should generate it.
        This is the 'completion' target for SFT.
        """
        parts = []
        if self.assistant_text:
            parts.append(self.assistant_text)
        for tag in self.action_tags:
            parts.append(f"[ACTION]{tag}[/ACTION]")
        for tag in self.shell_tags:
            parts.append(f"[SHELL]{tag}[/SHELL]")
        return "\n".join(parts)

    def format_chat_messages(self, system_prompt: str = "") -> list[dict]:
        """
        Convert to chat-format messages for training.

        Returns:
            [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": self.user_input})
        messages.append({"role": "assistant", "content": self.format_assistant_output()})
        return messages


# ─────────────────────── Validation ─────────────────────────────────────────

class ValidationError:
    def __init__(self, example_id: str, field: str, message: str):
        self.example_id = example_id
        self.field = field
        self.message = message

    def __str__(self):
        return f"[{self.example_id}] {self.field}: {self.message}"


def validate_example(ex: SFTExample) -> list[ValidationError]:
    """Validate a single SFT example for consistency."""
    errors = []

    # Required fields
    if not ex.id:
        errors.append(ValidationError(ex.id, "id", "Missing ID"))
    if not ex.user_input:
        errors.append(ValidationError(ex.id, "user_input", "Missing user input"))
    if ex.split not in ("train", "val", "test"):
        errors.append(ValidationError(ex.id, "split", f"Invalid split: {ex.split}"))

    # Scenario validation
    valid_scenarios = {s.value for s in Scenario}
    if ex.scenario not in valid_scenarios:
        errors.append(ValidationError(ex.id, "scenario", f"Unknown scenario: {ex.scenario}"))

    # Risk validation
    valid_risks = {r.value for r in RiskLabel}
    if ex.risk_level not in valid_risks:
        errors.append(ValidationError(ex.id, "risk_level", f"Invalid risk: {ex.risk_level}"))

    # Outcome validation
    valid_outcomes = {o.value for o in ExpectedOutcome}
    if ex.expected_outcome not in valid_outcomes:
        errors.append(ValidationError(ex.id, "expected_outcome", f"Invalid outcome: {ex.expected_outcome}"))

    # Consistency checks
    if ex.scenario == "conversational":
        if ex.action_tags or ex.shell_tags:
            errors.append(ValidationError(
                ex.id, "tags",
                "Conversational examples should have no action/shell tags"
            ))
        if ex.expected_outcome != "conversational":
            errors.append(ValidationError(
                ex.id, "expected_outcome",
                "Conversational scenario should have 'conversational' outcome"
            ))

    if ex.should_block and ex.risk_level != "critical":
        errors.append(ValidationError(
            ex.id, "should_block",
            "Only CRITICAL risk should have should_block=True"
        ))

    if ex.requires_confirmation and ex.risk_level not in ("high", "critical"):
        errors.append(ValidationError(
            ex.id, "requires_confirmation",
            "Confirmation should only be required for HIGH/CRITICAL risk"
        ))

    if ex.risk_level == "critical" and (ex.action_tags or ex.shell_tags):
        errors.append(ValidationError(
            ex.id, "tags",
            "CRITICAL risk examples should NOT have executable tags (model should refuse)"
        ))

    if ex.risk_level == "high" and not ex.requires_confirmation:
        errors.append(ValidationError(
            ex.id, "requires_confirmation",
            "HIGH risk should require confirmation"
        ))

    return errors


def validate_jsonl(filepath: str) -> tuple[int, int, list[ValidationError]]:
    """
    Validate an entire JSONL dataset file.

    Returns:
        (total_examples, valid_count, all_errors)
    """
    all_errors = []
    total = 0
    valid = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                ex = SFTExample.from_dict(data)
                errs = validate_example(ex)
                total += 1
                if not errs:
                    valid += 1
                else:
                    all_errors.extend(errs)
            except (json.JSONDecodeError, TypeError) as e:
                all_errors.append(ValidationError(
                    f"line_{line_num}", "json", f"Parse error: {e}"
                ))
                total += 1

    return total, valid, all_errors


# ─────────────────────── CLI ────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "--validate":
        print("Usage: python -m Jarvis.sft.schema --validate <path.jsonl>")
        sys.exit(1)

    filepath = sys.argv[2]
    total, valid, errors = validate_jsonl(filepath)

    print(f"\nValidation Results: {valid}/{total} examples valid")
    if errors:
        print(f"\n{len(errors)} error(s) found:")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)
    else:
        print("All examples passed validation!")
        sys.exit(0)
