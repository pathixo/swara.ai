#!/usr/bin/env python
import requests
import json
from Jarvis.core.personas import BUILTIN_PERSONAS

ollama_url = 'http://localhost:11434'
system_prompt = BUILTIN_PERSONAS['witty'].system_prompt

print('Testing /api/generate endpoint...')
payload_generate = {
    'model': 'jarvis-action',
    'prompt': 'open notepad',
    'system': system_prompt,
    'stream': False,
    'options': {
        'temperature': 0.7,
        'top_p': 0.9,
        'num_predict': 512,
    },
}

resp = requests.post(f'{ollama_url}/api/generate', json=payload_generate, timeout=30)
result = resp.json().get('response', '')
print(f'Response length: {len(result)} chars')
print(f'Has ACTION tags: {"[ACTION]" in result}')
print(f'Full response: {repr(result)}')
