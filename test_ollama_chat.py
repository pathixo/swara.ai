#!/usr/bin/env python
import requests
import json
from Jarvis.core.personas import BUILTIN_PERSONAS

ollama_url = 'http://localhost:11434'
system_prompt = BUILTIN_PERSONAS['witty'].system_prompt

print('Testing /api/chat endpoint...')
payload_chat = {
    'model': 'jarvis-action',
    'messages': [
        {
            'role': 'system',
            'content': system_prompt
        },
        {
            'role': 'user',
            'content': 'open notepad'
        }
    ],
    'stream': False,
    'options': {
        'temperature': 0.7,
        'top_p': 0.9,
        'num_predict': 512,
    },
}

try:
    resp = requests.post(f'{ollama_url}/api/chat', json=payload_chat, timeout=30)
    result = resp.json()
    print(f'Response: {result}')
    
    if 'message' in result:
        message_content = result['message'].get('content', '')
        print(f'Response length: {len(message_content)} chars')
        print(f'Has ACTION tags: {"[ACTION]" in message_content}')
        print(f'Full response: {repr(message_content)}')
except Exception as e:
    print(f'Error: {e}')
    print(f'Status code: {resp.status_code if resp else "N/A"}')
