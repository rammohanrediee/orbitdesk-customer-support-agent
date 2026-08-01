from time import perf_counter
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from orbitdesk_support_agent.model_config import (
    GENERATION_MODEL_NAME,
    GENERATION_MODEL_REVISION,
    MAX_NEW_TOKENS,
    get_device,)


class LocalLanguageModel:
    def __init__(
        self,
        tokenizer: Any | None = None,
        model: Any | None = None,
    ) -> None:
        self.device = get_device()
        load_started = perf_counter()

        self.tokenizer = tokenizer or AutoTokenizer.from_pretrained(
            GENERATION_MODEL_NAME,
            revision=GENERATION_MODEL_REVISION,
        )

        self.model = model or AutoModelForCausalLM.from_pretrained(
            GENERATION_MODEL_NAME,
            revision=GENERATION_MODEL_REVISION,
            dtype="auto",
        )

        self.model.to(self.device)
        self.model.eval()

        if tokenizer is not None and model is not None:
            self.model_load_seconds = 0.0
        else:
            self.model_load_seconds = perf_counter() - load_started

        self.last_generation_seconds = 0.0

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(
            formatted_prompt,
            return_tensors="pt",
        )

        inputs = {
            name: tensor.to(self.device)
            for name, tensor in inputs.items()
        }

        input_length = inputs["input_ids"].shape[1]
        generation_started = perf_counter()

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        self.last_generation_seconds = (
            perf_counter() - generation_started
        )

        generated_tokens = output_ids[0, input_length:]

        return self.tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
        ).strip()