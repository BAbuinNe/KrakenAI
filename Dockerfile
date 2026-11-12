FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV E5_MODEL_FILE=/srv/models/e5/model.onnx E5_TOKENIZER_FILE=/srv/models/e5/tokenizer.json
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt ./
# No torch: use a small ONNX runtime with quantized E5 weights instead.
RUN pip install --no-cache-dir -r requirements.txt "onnxruntime>=1.20,<2" "tokenizers>=0.20,<1" "numpy>=1.26,<3"
# Download model ONLY when building the image, never while handling customer files.
# The published E5-small int8 ONNX weight file is ~118 MB (not the 470 MB FP32 variant).
RUN pip install --no-cache-dir "huggingface_hub>=0.30,<2" && \
    mkdir -p /srv/models/e5 && \
    python -c "from huggingface_hub import hf_hub_download; import shutil,hashlib,pathlib; root=pathlib.Path('/srv/models/e5'); repo='intfloat/multilingual-e5-small'; path=hf_hub_download(repo_id=repo,filename='onnx/model_qint8_avx512_vnni.onnx'); assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()=='dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88'; shutil.copyfile(path,root/'model.onnx'); shutil.copyfile(hf_hub_download(repo_id=repo,filename='onnx/tokenizer.json'),root/'tokenizer.json')" && \
    pip uninstall -y huggingface_hub && rm -rf /root/.cache/huggingface
COPY app ./app
COPY benchmarks ./benchmarks
# Build-time model smoke test catches incompatible ONNX/tokenizer artifacts
# before a broken image can replace the live demo.
RUN python -c "from app.onnx_e5 import embed_onnx; v=embed_onnx(['query: оперативная память 16 ГБ','passage: RAM 16 GB']); assert len(v)==2 and all(len(x)==384 for x in v), 'E5 must produce 384-dimensional vectors'; print('E5 ONNX smoke OK')"
# Exercise the real FastAPI upload->analysis->ranking path during build.
RUN python -m app.smoke_sessions
RUN python -m app.smoke_chat
RUN python -m app.smoke_demo
RUN python -m app.smoke_workspace
RUN python -m app.smoke_history
# Ensure live ONNX + BM25 hybrid returns source-linked evidence and preserves FAIL.
RUN python -m app.smoke_evidence
# Offline benchmark: print comparable Recall@K / nDCG / MRR for lexical baselines and E5.
RUN python -m app.retrieval_benchmark --models tfidf bm25 e5 hybrid
RUN python -m app.workspace_benchmark --models bm25 e5 hybrid
# MiniLM research is reproducible via app.benchmark_minilm_build on demand;
# do not re-download it on every production deployment.
RUN useradd --create-home kraken && chown -R kraken:kraken /srv/models
USER kraken
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
