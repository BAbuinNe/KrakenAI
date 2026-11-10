"""Safe diagnostic regression coverage for Gemini streaming failures."""
import pytest
from app import ai
from app.ai_stream import ModelStreamError, from_http_status, build_payload

@pytest.mark.parametrize("status,code",[
    (400,"bad_request"),(401,"invalid_key"),(403,"access_denied"),
    (404,"model_not_found"),(429,"quota_exceeded"),(503,"provider_unavailable")
])
def test_provider_http_failures_have_safe_user_messages(status,code):
    exc=from_http_status(status)
    assert isinstance(exc,ModelStreamError)
    assert exc.code==code
    assert "Bearer " not in str(exc)
    assert "GEMINI_API_KEY=" not in str(exc)

def test_gemini_payload_allocates_room_for_visible_output(monkeypatch):
    monkeypatch.setenv("AI_BACKEND","gemini")
    monkeypatch.setenv("GEMINI_MODEL","gemini-3.8-flash")
    payload=build_payload([{"role":"user","content":"hello"}])
    assert payload["model"]=="gemini-3.8-flash"
    assert payload["max_tokens"]>=2048
    assert payload["reasoning_effort"]=="low"
    assert payload["stream"] is True

def test_ollama_payload_unchanged(monkeypatch):
    monkeypatch.setenv("AI_BACKEND","ollama")
    monkeypatch.setenv("AI_MODEL","qwen2.5:7b-instruct")
    payload=build_payload([{"role":"user","content":"hi"}])
    assert payload["options"]["num_ctx"]==8192
    assert "reasoning_effort" not in payload

def test_stream_error_categorization_does_not_expose_upstream_text():
    exc=from_http_status(429)
    assert "лимит" in str(exc)
    assert exc.status==429
