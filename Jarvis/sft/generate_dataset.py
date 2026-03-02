"""
Dataset Generator — Expand seed data using templates + app registry
=====================================================================
Generates a larger training dataset by combining:
  - App Registry aliases → app_launch / url_open examples
  - Risk patterns → dangerous / critical examples
  - Template variations → diverse phrasings

Usage:
    python -m Jarvis.sft.generate_dataset --out sft/train.jsonl --count 500
"""

import json
import os
import random
import argparse
from pathlib import Path

# ─────────────────────── Phrasing Templates ─────────────────────────────────

LAUNCH_TEMPLATES = [
    "open {app}",
    "launch {app}",
    "start {app}",
    "open {app} for me",
    "can you open {app}",
    "fire up {app}",
    "run {app}",
    "I need {app}",
    "open up {app} please",
    "start {app} please",
    "could you launch {app}",
    "bring up {app}",
    "I want to use {app}",
    "start up {app}",
    "{app} please",
]

LAUNCH_RESPONSES = [
    "Opening {display}.",
    "Launching {display} for you.",
    "Firing up {display}.",
    "Starting {display}.",
    "{display} is on its way.",
    "Right away. Opening {display}.",
    "Got it. Launching {display}.",
]

URL_TEMPLATES = [
    "open {app}",
    "go to {app}",
    "take me to {app}",
    "browse {app}",
    "open {app} in my browser",
    "I want to check {app}",
    "navigate to {app}",
    "pull up {app}",
    "can we go to {app}",
    "show me {app}",
    "open exactly {app}",
]

URL_RESPONSES = [
    "Opening {display}.",
    "Navigating to {display}.",
    "Taking you to {display}.",
    "Right away. Opening {display}.",
    "Here is {display}.",
]

SHELL_SAFE_EXAMPLES = [
    {"input": "create a folder named {name}", "cmd": "New-Item -ItemType Directory -Name '{name}' -Force",
     "response": "Creating folder '{name}'.", "risk": "low"},
    {"input": "what time is it", "cmd": "Get-Date -Format 'hh:mm:ss tt'",
     "response": "Let me check the time.", "risk": "low"},
    {"input": "show my username", "cmd": "$env:USERNAME",
     "response": "Checking your username.", "risk": "low"},
    {"input": "list files on the desktop", "cmd": "Get-ChildItem $env:USERPROFILE\\Desktop | Format-Table Name, Length -AutoSize",
     "response": "Here are the files on your Desktop:", "risk": "low"},
    {"input": "what's today's date", "cmd": "Get-Date -Format 'dddd, MMMM dd, yyyy'",
     "response": "Let me check today's date.", "risk": "low"},
    {"input": "show environment variables", "cmd": "Get-ChildItem Env: | Format-Table Name, Value -AutoSize",
     "response": "Here are your environment variables:", "risk": "low"},
    {"input": "check if python is installed", "cmd": "python --version",
     "response": "Checking Python installation.", "risk": "low"},
    {"input": "show wifi networks", "cmd": "netsh wlan show networks",
     "response": "Scanning for Wi-Fi networks.", "risk": "low"},
    {"input": "ping google", "cmd": "Test-Connection google.com -Count 4",
     "response": "Pinging Google.", "risk": "low"},
    {"input": "how much RAM do I have", "cmd": "(Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum / 1GB",
     "response": "Checking your RAM.", "risk": "low"},
]

CONVERSATIONAL_EXAMPLES = [
    {"input": "hello", "response": "Hello! How can I help you today?"},
    {"input": "hi there", "response": "Hi! What would you like me to do?"},
    {"input": "thanks", "response": "You're welcome! Let me know if you need anything else."},
    {"input": "good morning", "response": "Good morning! Ready to help."},
    {"input": "what's your name", "response": "I'm Jarvis, your AI assistant. How can I help?"},
    {"input": "who made you", "response": "I was built to be your personal AI assistant on Windows."},
    {"input": "tell me something interesting", "response": "Did you know that the first computer bug was an actual moth found in a Harvard Mark II computer in 1947?"},
    {"input": "you're awesome", "response": "Thank you! I do my best. What would you like me to do next?"},
    {"input": "what's the meaning of life", "response": "42, according to Douglas Adams. But I'm better at opening apps and running commands!"},
    {"input": "goodbye", "response": "Goodbye! I'll be here whenever you need me."},
]

DANGEROUS_TEMPLATES = [
    {"input": "delete all files in {folder}", "response": "⚠️ This will permanently delete all files in {folder}. Are you sure you want to proceed?",
     "risk": "high", "reason": "Recursive file deletion"},
    {"input": "remove {folder} and everything in it", "response": "⚠️ This will recursively delete {folder} and all its contents. This cannot be undone. Are you sure?",
     "risk": "high", "reason": "Recursive file deletion"},
    {"input": "shut down my computer", "response": "⚠️ This will shut down your computer immediately. Any unsaved work will be lost. Are you sure?",
     "risk": "high", "reason": "System shutdown"},
    {"input": "restart my PC now", "response": "⚠️ This will restart your computer. Any unsaved work will be lost. Shall I proceed?",
     "risk": "high", "reason": "System restart"},
    {"input": "change the execution policy", "response": "⚠️ Changing the PowerShell execution policy affects system security. Are you sure you want to modify it?",
     "risk": "high", "reason": "Execution policy change"},
    {"input": "kill the {service} service", "response": "⚠️ Stopping system services can affect Windows functionality. Are you sure you want to stop {service}?",
     "risk": "high", "reason": "Service stop"},
]

CRITICAL_TEMPLATES = [
    {"input": "format drive {drive}", "response": "I cannot format drive {drive}. This would destroy all data on the drive. This operation is blocked for safety.",
     "reason": "Disk format"},
    {"input": "run diskpart", "response": "I cannot run diskpart. This tool can modify disk partitions and cause data loss. This operation is blocked for safety.",
     "reason": "Disk partitioning"},
    {"input": "edit boot configuration", "response": "I cannot modify the boot configuration (bcdedit). This could prevent your system from starting. This operation is blocked for safety.",
     "reason": "Boot configuration edit"},
    {"input": "wipe drive {drive} securely", "response": "I cannot perform a secure disk wipe. This operation is blocked for safety as it would destroy all data.",
     "reason": "Secure disk wipe"},
]

FOLDER_NAMES = ["Downloads", "Documents", "Desktop", "temp", "old_files", "backup", "test_data", "Pictures", "Music", "Videos", "Source", "cache"]
SERVICE_NAMES = ["Windows Update", "Print Spooler", "Defender", "Firewall", "Bluetooth", "Audio", "WLAN AutoConfig", "Xbox Live"]
DRIVE_LETTERS = ["C", "D", "E", "F", "G", "Z", "X"]
RANDOM_NAMES = ["Projects", "Work", "Notes", "Archive", "Data", "Reports", "Logs", "Personal", "Drafts", "Finals", "Taxes2025"]


def load_app_registry() -> dict:
    """Load the app registry JSON."""
    registry_path = Path(__file__).parent.parent / "core" / "system" / "app_registry.json"
    with open(registry_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_app_examples(registry: dict, target_count: int, seen_inputs: set) -> list[dict]:
    """Generate app launch and URL open examples from registry."""
    examples = []
    app_items = list(registry.items())
    
    attempts = 0
    idx = 0
    while len(examples) < target_count and attempts < target_count * 10:
        attempts += 1
        app_key, app_data = random.choice(app_items)
        display = app_data["display_name"]
        aliases = app_data.get("aliases", [app_key])
        alias = random.choice(aliases)
        method = app_data.get("launch_method", "exe")
        target = app_data.get("launch_target", app_key)

        if method == "url":
            template = random.choice(URL_TEMPLATES)
            user_input = template.format(app=alias)
            if user_input in seen_inputs: continue
            seen_inputs.add(user_input)
            response = random.choice(URL_RESPONSES)
            examples.append({
                "id": f"gen_url_{idx:04d}",
                "split": random.choice(["train", "train", "train", "val"]),
                "scenario": "url_open",
                "user_input": user_input,
                "assistant_text": response.format(display=display),
                "action_tags": [f"open_url: {target}"],
                "shell_tags": [],
                "risk_level": "low",
                "requires_confirmation": False,
                "should_block": False,
                "expected_outcome": "executed",
            })
            idx += 1
        else:
            template = random.choice(LAUNCH_TEMPLATES)
            user_input = template.format(app=alias)
            if user_input in seen_inputs: continue
            seen_inputs.add(user_input)
            response = random.choice(LAUNCH_RESPONSES)
            examples.append({
                "id": f"gen_app_{idx:04d}",
                "split": random.choice(["train", "train", "train", "val"]),
                "scenario": "app_launch",
                "user_input": user_input,
                "assistant_text": response.format(display=display),
                "action_tags": [f"launch_app: {app_key}"],
                "shell_tags": [],
                "risk_level": "low",
                "requires_confirmation": False,
                "should_block": False,
                "expected_outcome": "executed",
            })
            idx += 1

    return examples


def generate_shell_examples(count: int, seen_inputs: set) -> list[dict]:
    """Generate safe shell command examples."""
    examples = []
    attempts = 0
    idx = 0
    while len(examples) < count and attempts < count * 10:
        attempts += 1
        base = random.choice(SHELL_SAFE_EXAMPLES)
        name = random.choice(RANDOM_NAMES)
        user_input = base["input"].format(name=name)
        if user_input in seen_inputs: continue
        seen_inputs.add(user_input)
        examples.append({
            "id": f"gen_shell_{idx:04d}",
            "split": random.choice(["train", "train", "train", "val"]),
            "scenario": "shell_safe",
            "user_input": user_input,
            "assistant_text": base["response"].format(name=name),
            "action_tags": [],
            "shell_tags": [base["cmd"].format(name=name)],
            "risk_level": base["risk"],
            "requires_confirmation": False,
            "should_block": False,
            "expected_outcome": "executed",
        })
        idx += 1
    return examples


def generate_danger_examples(count: int, seen_inputs: set) -> list[dict]:
    """Generate dangerous command examples (HIGH risk, confirmation required)."""
    examples = []
    attempts = 0
    idx = 0
    while len(examples) < count and attempts < count * 10:
        attempts += 1
        base = random.choice(DANGEROUS_TEMPLATES)
        folder = random.choice(FOLDER_NAMES)
        service = random.choice(SERVICE_NAMES)
        user_input = base["input"].format(folder=folder, service=service)
        if user_input in seen_inputs: continue
        seen_inputs.add(user_input)
        examples.append({
            "id": f"gen_danger_{idx:04d}",
            "split": random.choice(["train", "train", "val"]),
            "scenario": "shell_dangerous",
            "user_input": user_input,
            "assistant_text": base["response"].format(folder=folder, service=service),
            "action_tags": [],
            "shell_tags": [],
            "risk_level": "high",
            "requires_confirmation": True,
            "should_block": False,
            "expected_outcome": "confirmed",
        })
        idx += 1
    return examples


def generate_critical_examples(count: int, seen_inputs: set) -> list[dict]:
    """Generate CRITICAL examples (always blocked, no tags)."""
    examples = []
    attempts = 0
    idx = 0
    while len(examples) < count and attempts < count * 10:
        attempts += 1
        base = random.choice(CRITICAL_TEMPLATES)
        drive = random.choice(DRIVE_LETTERS)
        user_input = base["input"].format(drive=drive)
        if user_input in seen_inputs: continue
        seen_inputs.add(user_input)
        examples.append({
            "id": f"gen_critical_{idx:04d}",
            "split": random.choice(["train", "train", "val"]),
            "scenario": "shell_critical",
            "user_input": user_input,
            "assistant_text": base["response"].format(drive=drive),
            "action_tags": [],
            "shell_tags": [],
            "risk_level": "critical",
            "requires_confirmation": False,
            "should_block": True,
            "expected_outcome": "blocked",
        })
        idx += 1
    return examples


def generate_conversational_examples(count: int, seen_inputs: set) -> list[dict]:
    """Generate conversational examples (no tags)."""
    examples = []
    attempts = 0
    idx = 0
    while len(examples) < count and attempts < count * 10:
        attempts += 1
        base = random.choice(CONVERSATIONAL_EXAMPLES)
        user_input = base["input"]
        if user_input in seen_inputs: continue
        seen_inputs.add(user_input)
        examples.append({
            "id": f"gen_conv_{idx:04d}",
            "split": random.choice(["train", "train", "train", "val"]),
            "scenario": "conversational",
            "user_input": user_input,
            "assistant_text": base["response"],
            "action_tags": [],
            "shell_tags": [],
            "risk_level": "low",
            "requires_confirmation": False,
            "should_block": False,
            "expected_outcome": "conversational",
        })
        idx += 1
    return examples


def generate_dataset(total_count: int, output_path: str) -> None:
    """Generate a balanced dataset with the target count of examples."""
    registry = load_app_registry()
    
    seen_inputs = set()
    all_examples = []
    
    # Load seed data
    seed_path = Path(__file__).parent / "seed_dataset.jsonl"
    if seed_path.exists():
        with open(seed_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ex = json.loads(line)
                    if ex["user_input"] not in seen_inputs:
                        seen_inputs.add(ex["user_input"])
                        all_examples.append(ex)

    # Distribution: 30% app, 10% url, 25% shell_safe, 15% danger, 5% critical, 15% conv
    n_app = int(total_count * 0.30)
    n_url = int(total_count * 0.10)
    n_shell = int(total_count * 0.25)
    n_danger = int(total_count * 0.15)
    n_critical = int(total_count * 0.05)
    n_conv = total_count - n_app - n_url - n_shell - n_danger - n_critical

    all_examples.extend(generate_app_examples(registry, n_app + n_url, seen_inputs))
    all_examples.extend(generate_shell_examples(n_shell, seen_inputs))
    all_examples.extend(generate_danger_examples(n_danger, seen_inputs))
    all_examples.extend(generate_critical_examples(n_critical, seen_inputs))
    all_examples.extend(generate_conversational_examples(n_conv, seen_inputs))

    # Shuffle
    random.shuffle(all_examples)

    # Write
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # Stats
    scenarios = {}
    splits = {}
    for ex in all_examples:
        scenarios[ex["scenario"]] = scenarios.get(ex["scenario"], 0) + 1
        splits[ex["split"]] = splits.get(ex["split"], 0) + 1

    print(f"\nGenerated {len(all_examples)} examples -> {output_path}")
    print(f"\nScenario distribution:")
    for s, c in sorted(scenarios.items()):
        print(f"  {s:25s} {c:5d}  ({100*c/len(all_examples):.1f}%)")
    print(f"\nSplit distribution:")
    for s, c in sorted(splits.items()):
        print(f"  {s:10s} {c:5d}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate SFT training data")
    parser.add_argument("--out", default="Jarvis/sft/train.jsonl", help="Output JSONL path")
    parser.add_argument("--count", type=int, default=500, help="Target example count")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    generate_dataset(args.count, args.out)
