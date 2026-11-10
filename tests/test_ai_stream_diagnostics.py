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

@pytest.mark.parametrize("failures", [1, 2])
def test_retry_transient_gemini_503_then_stream_success(monkeypatch,failures):
    import asyncio
    import httpx
    from app import ai_stream
    monkeypatch.setenv("AI_BACKEND","gemini")
    monkeypatch.setenv("GEMINI_MODEL","gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_API_KEY","test-local-do-not-send")
    calls=[]
    def handler(req):
        calls.append(req)
        if len(calls)<=failures:
            return httpx.Response(503,request=req,text='private error: do not reveal')
        return httpx.Response(200,request=req,headers={"Content-Type":"text/event-stream"},
          text='data: {"choices":[{"delta":{"content":"Привет!"}}]}\n\ndata: [DONE]\n\n')
    real_client=httpx.AsyncClient
    monkeypatch.setattr(ai_stream.httpx,"AsyncClient",
      lambda **kwargs: real_client(transport=httpx.MockTransport(handler),**kwargs))
    async def no_wait(_): pass
    monkeypatch.setattr(ai_stream.asyncio,"sleep",no_wait)
    async def collect():
        return [text async for text in ai_stream.stream_answer("Привет",None,[])]
    assert asyncio.run(collect())==["Привет!"]
    assert len(calls)==failures+1
    assert all(req.url.host=="generativelanguage.googleapis.com" for req in calls)

def test_no_retry_on_gemini_429(monkeypatch):
    import asyncio
    import httpx
    from app import ai_stream
    monkeypatch.setenv("AI_BACKEND","gemini")
    monkeypatch.setenv("GEMINI_MODEL","gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_API_KEY","test-only")
    attempts=[]
    def handler(req):
        attempts.append(req)
        return httpx.Response(429,request=req)
    real_client=httpx.AsyncClient
    monkeypatch.setattr(ai_stream.httpx,"AsyncClient",
      lambda **kwargs: real_client(transport=httpx.MockTransport(handler),**kwargs))
    async def collect():
        return [text async for text in ai_stream.stream_answer("Привет",None,[])]
    with pytest.raises(ModelStreamError) as exc:
        asyncio.run(collect())
    assert exc.value.status==429
    assert len(attempts)==1

def test_gemini_completion_retries_transient_503(monkeypatch):
    import asyncio
    import httpx
    monkeypatch.setenv("AI_BACKEND","gemini")
    monkeypatch.setenv("GEMINI_MODEL","gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_API_KEY","test-only")
    calls=[]
    def handler(req):
        calls.append(req)
        if len(calls)==1: return httpx.Response(503,request=req)
        return httpx.Response(200,request=req,
          json={"choices":[{"message":{"content":"{\"observations\":[]}"}}]})
    real_client=httpx.AsyncClient
    monkeypatch.setattr(ai.httpx,"AsyncClient",
      lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    async def no_wait(_): pass
    monkeypatch.setattr(ai.asyncio,"sleep",no_wait)
    res=asyncio.run(ai._completion([{"role":"user","content":"Проверка"}]))
    assert res=='{"observations":[]}'
    assert len(calls)==2
    assert "temperature" not in __import__('json').loads(calls[-1].content)
