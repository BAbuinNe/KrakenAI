"""Ollama bridge for private inference, guarded against arbitrary outbound URLs."""
from __future__ import annotations
import os
from urllib.parse import urlparse
import httpx

_ALLOWED_HOSTS = frozenset({'127.0.0.1', 'localhost', 'ollama'})

def ollama_url() -> str:
    url = os.getenv('OLLAMA_URL', 'http://ollama:11434/api/chat')
    p = urlparse(url)
    if (p.scheme != 'http' or p.hostname not in _ALLOWED_HOSTS
            or p.port != 11434 or p.path != '/api/chat'
            or p.username or p.password or p.params or p.query or p.fragment):
        raise ValueError('OLLAMA_URL должен указывать на локальный Ollama:11434/api/chat')
    return url

async def chat(messages: list[dict[str, str]], max_tokens: int = 800) -> str:
    model = os.getenv('AI_MODEL', '').strip()
    if not model:
        raise RuntimeError('AI_MODEL не задан')
    payload = {
        'model': model,
        'messages': messages,
        'stream': False,
        'options': {'temperature': 0, 'num_predict': min(max_tokens, 1500), 'num_ctx': 8192},
    }
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(100, connect=3),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        response = await client.post(ollama_url(), json=payload)
        response.raise_for_status()
        body = response.json()
    answer = body.get('message', {}).get('content')
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError('Пустой ответ Ollama')
    return answer[:14000]
