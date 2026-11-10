"""Local model routing and SSRF regressions."""
import asyncio
import pytest
from unittest.mock import AsyncMock
from app import ai,local_ai

def test_local_mode_without_cloud_key(monkeypatch):
    monkeypatch.setenv('AI_BACKEND','ollama')
    monkeypatch.setenv('AI_MODEL','qwen2.5:7b-instruct')
    monkeypatch.delenv('AI_API_KEY',raising=False)
    assert ai.enabled()

def test_remote_requires_key(monkeypatch):
    monkeypatch.setenv('AI_BACKEND','remote')
    monkeypatch.setenv('AI_MODEL','qwen2.5:7b-instruct')
    monkeypatch.delenv('AI_API_KEY',raising=False)
    assert not ai.enabled()

@pytest.mark.parametrize('url',[
    'https://example.com/api/chat',
    'http://example.com:11434/api/chat',
    'http://127.0.0.1:1234/api/chat',
    'http://127.0.0.1:11434/admin',
    'http://ollama:11434/api/chat?x=1',
    'http://user:password@ollama:11434/api/chat',
])
def test_reject_external_ollama_url(monkeypatch,url):
    monkeypatch.setenv('OLLAMA_URL',url)
    with pytest.raises(ValueError):local_ai.ollama_url()

def test_accept_local_ollama(monkeypatch):
    monkeypatch.setenv('OLLAMA_URL','http://ollama:11434/api/chat')
    assert local_ai.ollama_url().endswith(':11434/api/chat')

def test_ai_completion_routes_to_local_client(monkeypatch):
    monkeypatch.setenv('AI_BACKEND','ollama')
    monkeypatch.setenv('AI_MODEL','qwen2.5:7b-instruct')
    fake=AsyncMock(return_value='локальный ответ')
    monkeypatch.setattr(local_ai,'chat',fake)
    assert asyncio.run(ai._completion([{'role':'user','content':'проверка'}]))=='локальный ответ'
    fake.assert_awaited_once()


def test_gemini_backend_configuration_is_explicit_and_pinned(monkeypatch):
    monkeypatch.setenv('AI_BACKEND','gemini')
    monkeypatch.setenv('GEMINI_MODEL','gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY','local-test-only')
    monkeypatch.setenv('AI_CHAT_COMPLETIONS_URL','https://attacker.invalid/steal')
    assert ai.enabled()
    assert ai._model()=='gemini-2.5-flash'
    assert ai._url()==ai.GEMINI_COMPLETIONS_URL
    assert ai._api_key()=='local-test-only'

def test_gemini_disabled_without_server_key(monkeypatch):
    monkeypatch.setenv('AI_BACKEND','gemini')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setenv('GEMINI_MODEL','gemini-2.5-flash')
    assert not ai.enabled()
