"""Memory-conscious ONNX inference for E5 Small on a 512-MiB demo instance.

The model and tokenizer are downloaded at image BUILD time; no Hugging Face
download is attempted while a user's request is being processed.
"""
from __future__ import annotations

import os
import threading
from typing import Any

_INSTANCE = None
_LOCK = threading.Lock()


class OnnxE5:
    def __init__(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(
            os.getenv("E5_TOKENIZER_FILE", "/srv/models/e5/tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=384)
        self.session = ort.InferenceSession(
            os.getenv("E5_MODEL_FILE", "/srv/models/e5/model.onnx"),
            sess_options=self._options(ort),
            providers=["CPUExecutionProvider"])
        self.input_names = {node.name for node in self.session.get_inputs()}
        self.output_name = self.session.get_outputs()[0].name

    @staticmethod
    def _options(ort: Any):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.enable_mem_pattern = False
        opts.enable_cpu_mem_arena = False
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        return opts

    def encode(self, texts: list[str]) -> list[list[float]]:
        import numpy as np
        vectors = []
        # Tiny batches to avoid request bursts on low-memory instances.
        for index in range(0, len(texts), 2):
            samples = self.tokenizer.encode_batch(texts[index:index + 2])
            maximum = max(len(sample.ids) for sample in samples)
            ids = np.asarray(
                [sample.ids + [0] * (maximum - len(sample.ids)) for sample in samples],
                dtype=np.int64)
            mask = np.asarray(
                [sample.attention_mask + [0] * (maximum-len(sample.attention_mask))
                 for sample in samples], dtype=np.int64)
            typ = np.zeros_like(ids)
            feeds = {"input_ids": ids, "attention_mask": mask, "token_type_ids": typ}
            output = self.session.run(
                [self.output_name],
                {key: value for key, value in feeds.items() if key in self.input_names})[0]
            # E5 specification: attention-mask-weighted mean pooling.
            expanded = mask[:, :, None].astype(np.float32)
            pooled = (output * expanded).sum(axis=1) / np.maximum(
                expanded.sum(axis=1), 1e-9)
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
            vectors.extend(pooled.tolist())
        return vectors


def embed_onnx(texts: list[str]) -> list[list[float]]:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = OnnxE5()
        return _INSTANCE.encode(texts)
