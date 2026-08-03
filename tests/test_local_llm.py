from unittest.mock import patch

from orbitdesk_support_agent import local_llm
from orbitdesk_support_agent.model_config import (
    MAX_NEW_TOKENS,
    MPS_MEMORY_FRACTION,
)


def test_generation_limit_is_safe_for_low_memory_macs() -> None:
    assert MAX_NEW_TOKENS == 192


def test_configure_device_memory_caps_mps_allocator() -> None:
    with patch.object(
        local_llm.torch.mps,
        "set_per_process_memory_fraction",
    ) as set_fraction:
        local_llm.configure_device_memory("mps")

    set_fraction.assert_called_once_with(MPS_MEMORY_FRACTION)


def test_configure_device_memory_ignores_non_mps_devices() -> None:
    with patch.object(
        local_llm.torch.mps,
        "set_per_process_memory_fraction",
    ) as set_fraction:
        local_llm.configure_device_memory("cpu")

    set_fraction.assert_not_called()


def test_release_device_cache_clears_mps_cache() -> None:
    with patch.object(local_llm.torch.mps, "empty_cache") as empty_cache:
        local_llm.release_device_cache("mps")

    empty_cache.assert_called_once_with()


def test_release_device_cache_ignores_non_mps_devices() -> None:
    with patch.object(local_llm.torch.mps, "empty_cache") as empty_cache:
        local_llm.release_device_cache("cpu")

    empty_cache.assert_not_called()
