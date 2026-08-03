from typing import Literal

import torch


Device = Literal["mps", "cuda", "cpu"]


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
GENERATION_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

# Replace "main" with exact commit hashes after downloading the models.
EMBEDDING_MODEL_REVISION = (
    "1110a243fdf4706b3f48f1d95db1a4f5529b4d41")

GENERATION_MODEL_REVISION = (
    "989aa7980e4cf806f80c7fef2b1adb7bc71aa306")

MAX_RETRIEVED_RECORDS = 4
MAX_NEW_TOKENS = 192
MPS_MEMORY_FRACTION = 0.55


def get_device() -> Device:
    if torch.backends.mps.is_available():
        return "mps"

    if torch.cuda.is_available():
        return "cuda"

    return "cpu"
