"""Private E5 Small inference service; deploy separately from the low-RAM web app.

Requires E5_SERVICE_TOKEN in environment and e5-specific dependencies.
Bind via uvicorn app.e5_server:app --host 0.0.0.0 --port 8000.
"""
from __future__ import annotations
import os
import secrets
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .embedding_search import _local_embed, _normalized

app = FastAPI(title="Kraken E5", docs_url=None, redoc_url=None, openapi_url=None)


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)


@app.get("/healthz")
def health():
    return {"ok": True}


@app.post("/embed")
def embed(request: EmbeddingRequest, authorization: str | None = Header(default=None)):
    token = os.getenv("E5_SERVICE_TOKEN", "")
    if not token or not authorization or not secrets.compare_digest(
            authorization, "Bearer " + token):
        raise HTTPException(401, "Unauthorized")
    if any(not item or len(item)>1800 for item in request.texts):
        raise HTTPException(422, "Invalid text length")
    try:
        vectors = _local_embed(request.texts)
        return {"vectors": [_normalized(row) for row in vectors]}
    except (RuntimeError, OSError, ImportError, ValueError):
        raise HTTPException(503, "Embedding model unavailable") from None
