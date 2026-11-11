"""Optional one-time MiniLM ONNX benchmark during Docker build.

MiniLM weights are downloaded to a temporary directory and removed. They are
NOT shipped to/loaded on the 512-MiB Render Free production instance.
Failure is explicitly reported; E5 deployment remains unaffected.
"""
from __future__ import annotations
import json
import os
import pathlib
import tempfile
from .retrieval_benchmark import run

REPO="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
WEIGHTS="onnx/model_qint8_avx512_vnni.onnx"
DATASET=pathlib.Path("benchmarks/ru_procurement_synthetic_v1.json")


def main():
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("MINILM_STATUS: skipped (huggingface_hub unavailable)",flush=True)
        return
    with tempfile.TemporaryDirectory(prefix="minilm-test-") as folder:
        # Do not let a failed optional model download break the public web app.
        try:
            model=hf_hub_download(repo_id=REPO,filename=WEIGHTS,local_dir=folder)
            tokenizer=hf_hub_download(repo_id=REPO,filename="tokenizer.json",local_dir=folder)
            os.environ["MINILM_ONNX_MODEL"]=str(pathlib.Path(model).resolve())
            os.environ["MINILM_ONNX_TOKENIZER"]=str(pathlib.Path(tokenizer).resolve())
            result=run(["minilm"],DATASET)
            if result["failures"]:
                print("MINILM_STATUS: "+json.dumps(result["failures"],ensure_ascii=False),flush=True)
            else:
                compact=result["model_results"][0]
                print("MINILM_STATUS: measured",flush=True)
                print("MINILM_METRICS: "+json.dumps(
                    {"model":compact["model"],"metrics":compact["metrics"],
                     "seconds":compact["seconds"],"queries":compact["queries"],
                     "passages":compact["passages"]},
                    ensure_ascii=False),flush=True)
        except Exception as exc:
            print("MINILM_STATUS: unmeasured - "+str(exc)[:230],flush=True)


if __name__=="__main__":
    main()
