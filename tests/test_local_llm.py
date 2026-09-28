from orbitdesk_support_agent.local_llm import LocalLanguageModel
from orbitdesk_support_agent.openrouter_llm import OpenRouterLanguageModel


def test_legacy_local_model_name_points_to_openrouter_backend() -> None:
    assert LocalLanguageModel is OpenRouterLanguageModel
