from langgraph.graph import StateGraph, END, START
from .state import AgentState
from .nodes import (
    intent_node,
    prompt_menu_node,
    greeting_node,
    browse_products_node,
    track_order_node,
    faq_node,
    after_sales_menu_node,
    human_agent_node,
    farewell_node,
    rating_node,
)
from .nodes_after_sales import (
    warranty_node,
    return_node,
    exchange_node,
    maintenance_node,
    complaint_node,
)


def route_by_intent(state: AgentState) -> str:
    """Route to the correct node based on detected intent."""
    intent = state.get("intent", "prompt_menu")
    routes = {
        "greeting":          "greeting",
        "browse_products":   "browse_products",
        "track_order":       "track_order",
        "faq":               "faq",
        "after_sales_menu":  "after_sales_menu",
        "return_product":    "return_product",
        "exchange_product":  "exchange_product",
        "warranty":          "warranty",
        "maintenance":       "maintenance",
        "complaint":         "complaint",
        "human_agent":       "human_agent",
        "prompt_menu":       "prompt_menu",
        "farewell":          "farewell",
        "rating":            "rating",
    }
    return routes.get(intent, "prompt_menu")


def build_graph():
    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("intent",          intent_node)
    graph.add_node("prompt_menu",     prompt_menu_node)
    graph.add_node("greeting",        greeting_node)
    graph.add_node("browse_products", browse_products_node)
    graph.add_node("track_order",     track_order_node)
    graph.add_node("faq",             faq_node)
    graph.add_node("after_sales_menu",after_sales_menu_node)
    graph.add_node("return_product",  return_node)
    graph.add_node("exchange_product",exchange_node)
    graph.add_node("warranty",        warranty_node)
    graph.add_node("maintenance",     maintenance_node)
    graph.add_node("complaint",       complaint_node)
    graph.add_node("human_agent",     human_agent_node)
    graph.add_node("farewell",        farewell_node)
    graph.add_node("rating",          rating_node)

    # Entry point
    graph.add_edge(START, "intent")

    # Conditional routing after intent detection
    graph.add_conditional_edges("intent", route_by_intent, {
        "greeting":          "greeting",
        "browse_products":   "browse_products",
        "track_order":       "track_order",
        "faq":               "faq",
        "after_sales_menu":  "after_sales_menu",
        "return_product":    "return_product",
        "exchange_product":  "exchange_product",
        "warranty":          "warranty",
        "maintenance":       "maintenance",
        "complaint":         "complaint",
        "human_agent":       "human_agent",
        "prompt_menu":       "prompt_menu",
        "farewell":          "farewell",
        "rating":            "rating",
    })

    # All nodes end the flow
    for node in [
        "prompt_menu", "greeting", "browse_products", "track_order",
        "faq", "after_sales_menu", "return_product", "exchange_product",
        "warranty", "maintenance", "complaint", "human_agent",
        "farewell", "rating",
    ]:
        graph.add_edge(node, END)

    return graph.compile()


# Build once at startup
agent_graph = build_graph()