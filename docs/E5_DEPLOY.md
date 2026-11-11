# E5 Small semantic retrieval deployment

The front-end and original API still support PDF/DOCX/XLSX/TXT input. Gemini remains enabled for chat and optional insights, never for obligatory numerical comparisons.

## Resources & architecture

The main Render service is currently configured as **free** (512 MB RAM). Loading PyTorch and the 118M-parameter multilingual-e5-small model in that process is unsafe; keep it separate. The model server requires an instance with adequate measured RAM (start benchmark around 2 GB), and may incur charges. Do NOT create/upgrade paid hosting without consent.

- Main app: fastapi `app.main` on Render, `EVIDENCE_RERANKER=e5`, `E5_SERVICE_URL=https://your-e5-host`, `E5_SERVICE_TOKEN` (secret, same value as service).
- E5 model service: `Dockerfile.e5`, start `app.e5_server:app`, `E5_SERVICE_TOKEN` environment secret. Endpoint `POST /embed` requires bearer token and accepts up to 32 strings. Service should be network-isolated where possible; HTTPS is mandatory in production.
- Local developer testing: `pip install -r requirements-e5.txt`, set `EVIDENCE_RERANKER=e5` and `E5_ENABLE_LOCAL=1` on a sufficiently provisioned machine. The main service can use a local E5 model only if enabled explicitly.

Model: `intfloat/multilingual-e5-small` (384-dimensional vectors). Source: https://huggingface.co/intfloat/multilingual-e5-small . E5 recommends `query: ` and `passage: ` prefixes. Similarity is computed as a dot product of unit-normalized vectors (cosine similarity).

Large inputs: `split_passages` chunks long lines, keeps original line/page information, and caps candidate counts for memory safety. **The older parser still truncates extracted text at 60,000 characters**. Until that is redesigned, do not claim full long-document coverage.

## Accuracy

The retrieval model returns ranked snippets, not fulfillment verdicts or an overall supplier score. Existing deterministic requirements checks still run before ranking and prevent recommendations if mandatory details are unknown or failed. Gemini stays available for chat and optional supplemental commentary.

## Production verification checklist

1. Confirm the Render workspace, deployed app service and actual public URL.
2. Approve any upgrade to a paid instance or creation of paid model hosting.
3. Deploy the E5 inference container, configure matching `E5_SERVICE_TOKEN`.
4. Point main service to private inference URL and set `EVIDENCE_RERANKER=e5`.
5. Verify `/healthz` for both services, `POST /api/analysis-jobs`, job polling, and real `evidence_retrieval.mode=e5`.
6. Benchmark CPU/RAM, check logs for 502 and compare Recall@5 with lexical search.

If E5 unavailable, numerical checks continue and result is explicitly marked unavailable, **never reported as E5 success**.
