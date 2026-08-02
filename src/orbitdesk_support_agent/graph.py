from langgraph.graph import END, START, StateGraph

from orbitdesk_support_agent.generator import LanguageModel
from orbitdesk_support_agent.nodes import (
    SemanticRetrieverProtocol,
    create_clarification_node,
    create_generation_node,
    create_out_of_scope_node,
    create_retrieval_node,
    create_retry_node,
    create_safe_failure_node,
    create_triage_node,
    create_verification_node,
    route_after_triage,
    route_after_verification,
)
from orbitdesk_support_agent.state import AgentState


def build_graph(
    llm: LanguageModel,
    semantic_retriever: SemanticRetrieverProtocol,
):
    graph = StateGraph(AgentState)

    graph.add_node(
        "triage",
        create_triage_node(llm),
    )
    graph.add_node(
        "retrieve",
        create_retrieval_node(semantic_retriever),
    )
    graph.add_node(
        "generate",
        create_generation_node(llm),
    )
    graph.add_node(
        "verify",
        create_verification_node(),
    )
    graph.add_node(
        "retry",
        create_retry_node(),
    )
    graph.add_node(
        "safe_failure",
        create_safe_failure_node(),
    )
    graph.add_node(
        "clarification",
        create_clarification_node(),
    )
    graph.add_node(
        "out_of_scope",
        create_out_of_scope_node(),
    )

    graph.add_edge(START, "triage")

    graph.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "retrieve": "retrieve",
            "clarification": "clarification",
            "out_of_scope": "out_of_scope",
            "safe_failure": "safe_failure",
        },
    )

    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "verify")

    graph.add_conditional_edges(
        "verify",
        route_after_verification,
        {
            "complete": END,
            "retry": "retry",
            "safe_failure": "safe_failure",
        },
    )

    graph.add_edge("retry", "generate")

    graph.add_edge("clarification", END)
    graph.add_edge("out_of_scope", END)
    graph.add_edge("safe_failure", END)

    return graph.compile()