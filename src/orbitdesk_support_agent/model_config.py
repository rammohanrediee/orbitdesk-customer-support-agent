from typing import Literal


Device = Literal["mps", "cuda", "cpu"]


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Replace "main" with exact commit hashes after downloading the models.
EMBEDDING_MODEL_REVISION = (
    "1110a243fdf4706b3f48f1d95db1a4f5529b4d41")

MAX_RETRIEVED_RECORDS = 4


def get_device() -> Device:
    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.backends.mps.is_available():
        return "mps"

    if torch.cuda.is_available():
        return "cuda"

    return "cpu"
