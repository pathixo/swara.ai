"""Quick integration test: validates jarvis-action model with real system prompt."""
import requests
from Jarvis.core.brain import DEFAULT_SYSTEM_PROMPT

tests = [
    "open notepad",
    "go to youtube",
    "list files in the current directory",
    "delete everything in Downloads",
    "tell me a joke",
    "how much disk space do I have",
    "shutdown my computer",
    "open chrome and go to github",
]

for t in tests:
    r = requests.post("http://localhost:11434/api/generate", json={
        "model": "jarvis-action",
        "prompt": t,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 200}
    }, timeout=60)
    resp = r.json()["response"]
    print(f"USER: {t}")
    print(f"JARVIS: {resp}")
    
    # Check for expected tags
    has_action = "[ACTION]" in resp
    has_shell = "[SHELL]" in resp
    has_tag = has_action or has_shell
    print(f"  -> Tags: ACTION={has_action} SHELL={has_shell}")
    print("---")
