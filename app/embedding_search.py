"""Semantic evidence retrieval using intfloat/multilingual-e5-small.

Only selects source snippets; it never changes PASS / FAIL / UNKNOWN.
Supports a separate private HTTP inference service or a local CPU model.
Both paths use the official E5 query:/passage: prefixes and normalized vectors.
"""
from __future__ import annotations
import math
import os
import re
from typing import Any

_MODEL_ID = "intfloat/multilingual-e5-small"
_LOCAL_MODEL = None
_SECTION = re.compile(r"^(?:Страница\s+\d+:|Лист:\s*.+)$", re.I)
_TOKENS = re.compile(r"\S+")


def split_passages(text: str, max_chars: int = 840, overlap: int = 100,
                   max_passages: int = 400) -> list[dict[str, Any]]:
    """Preserve source line/page and chunk very long lines without losing content.

    Character limit is intentionally conservative vs E5's 512-token window.
    Embedding model truncation must still be monitored for pathological strings.
    """
    out = []
    location = "строка"
    for index, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if _SECTION.fullmatch(line):
            location = line[:-1] if line.endswith(":") else line
            continue
        # Keep a single original row/paragraph intact if possible. Carry
        # overlap for lines that exceed max_chars, preserving their line number.
        pos = 0
        while pos < len(line):
            part = line[pos:pos + max_chars].strip()
            if part:
                out.append({"quote": part, "line": index, "location": location})
            if len(out) >= max_passages:
                return out
            if pos + max_chars >= len(line):
                break
            pos += max_chars - overlap
    return out


def _normalized(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("Empty embedding")
    vector = [float(x) for x in values]
    if any(not math.isfinite(x) for x in vector):
        raise ValueError("Non-finite embedding")
    norm = math.sqrt(sum(x * x for x in vector))
    if norm <= 1e-12:
        raise ValueError("Zero embedding")
    return [x / norm for x in vector]


def _local_embed(texts: list[str]) -> list[list[float]]:
    global _LOCAL_MODEL
    if _LOCAL_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _LOCAL_MODEL = SentenceTransformer(_MODEL_ID, device="cpu")
    vectors = _LOCAL_MODEL.encode(
        texts, batch_size=8, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=False
    )
    return [[float(v) for v in row] for row in vectors]


def embed(texts: list[str]) -> list[list[float]]:
    """Embedding service must return JSON {'vectors': [[...], ...]}."""
    url = os.getenv("E5_SERVICE_URL", "").strip()
    if url:
        import httpx
        if not url.startswith("https://") and not (
                os.getenv("APP_ENV") != "production" and
                url.startswith("http://127.0.0.1:")):
            raise ValueError("E5_SERVICE_URL must use HTTPS")
        token = os.getenv("E5_SERVICE_TOKEN", "")
        if not token:
            raise ValueError("E5_SERVICE_TOKEN is missing")
        with httpx.Client(timeout=httpx.Timeout(55, connect=5),
                          follow_redirects=False, trust_env=False) as client:
            response = client.post(
                url.rstrip("/") + "/embed",
                json={"texts": texts},
                headers={"Authorization": "Bearer " + token})
            response.raise_for_status()
            result = response.json()["vectors"]
    else:
        if os.getenv("E5_ENABLE_LOCAL") != "1":
            raise RuntimeError("E5 service is not configured")
        result = _local_embed(texts)
    if len(result) != len(texts):
        raise ValueError("Embedding count mismatch")
    normalized = [_normalized(row) for row in result]
    if len({len(v) for v in normalized}) != 1:
        raise ValueError("Embedding dimension mismatch")
    return normalized


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vector dimension mismatch")
    return sum(x*y for x, y in zip(a, b))


def retrieve_e5(result: dict[str, Any], offers: list[tuple[str, str]],
                max_checks: int = 80, top_k: int = 3) -> dict[str, Any]:
    """Search chunked proposals using cosine similarity; no vendor grading."""
    groups = []
    all_texts = []
    queries = []
    for supplier in result.get("suppliers", [])[:10]:
        name = str(supplier.get("name", ""))
        text = next((body for offer_name, body in offers if offer_name == name), "")
        passages = split_passages(text)
        if not passages:
            continue
        checks = supplier.get("checks", [])[:max_checks]
        reqs = []
        for check in checks:
            rq = (str(check.get("parameter") or "") + ": " +
                  str(check.get("requirement_source") or ""))[:800]
            if rq.strip(" :"):
                reqs.append((check, rq))
        if not reqs:
            continue
        groups.append((name, passages, reqs))
        all_texts.extend(["passage: " + p["quote"] for p in passages])
        queries.extend(["query: " + rq for _, rq in reqs])
    if not groups:
        return {"mode": "none", "model": None, "results": [],
                "note": "Нет доступных фрагментов для поиска"}
    # Service API is bounded to avoid huge one-shot requests and OOM.
    docs = []
    for i in range(0, len(all_texts), 32):
        docs.extend(embed(all_texts[i:i+32]))
    unique_queries = list(dict.fromkeys(queries))
    query_vectors = {}
    for i in range(0, len(unique_queries), 32):
        batch = unique_queries[i:i+32]
        query_vectors.update(zip(batch, embed(batch)))
    results = []
    offset = 0
    for name, passages, reqs in groups:
        vectors = docs[offset:offset+len(passages)]
        offset += len(passages)
        for check, rq in reqs:
            q = query_vectors["query: " + rq]
            scored = sorted(
                ((cosine(q, vector), passage) for passage, vector in zip(passages, vectors)),
                key=lambda pair: -pair[0])[:top_k]
            results.append({
                "supplier": name,
                "parameter": str(check.get("parameter") or "")[:120],
                "requirement_source": str(check.get("requirement_source") or "")[:300],
                "fragments": [
                    {"quote": passage["quote"], "line": passage["line"],
                     "location": passage["location"],
                     "relevance_score": round(score, 4)}
                    for score, passage in scored]})
    return {"mode": "e5", "model": _MODEL_ID, "results": results,
            "note": "Косинусная близость эмбеддингов; не вероятность выполнения ТЗ"}
