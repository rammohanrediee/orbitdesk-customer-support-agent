from typing import Literal

import torch


Device = Literal["mps", "cuda", "cpu"]


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
GENERATION_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

# Replace "main" with exact commit hashes after downloading the models.
EMBEDDING_MODEL_REVISION = "main"
GENERATION_MODEL_REVISION = "main"

MAX_RETRIEVED_RECORDS = 4
MAX_NEW_TOKENS = 512


def get_device() -> Device:
    if torch.backends.mps.is_available():
        return "mps"

    if torch.cuda.is_available():
        return "cuda"

    return "cpu"