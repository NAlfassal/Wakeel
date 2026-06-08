from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):

    # Full conversation history — LangGraph appends automatically
    messages: Annotated[list, add_messages]

    # Customer's WhatsApp number (unique session identifier)
    user_phone: str

    # Intent detected by intent_node (e.g. "greeting", "faq", "track_order")
    intent: Optional[str]

    # Final reply text to send to the customer
    reply_text: Optional[str]

    # Reply type: "text" | "list"
    reply_type: str

    # Payload for WhatsApp list messages (header, body, sections)
    list_data: Optional[dict]

    # True once the conversation has been formally closed
    is_done: bool

    # ── Session tracking ──────────────────────────────────────────────

    # Current session state — controls how numbers and free text are interpreted
    # Values: fresh | menu | products | orders | policy | after_sales
    #         return_awaiting | exchange_awaiting | maintenance_awaiting
    #         complaint_awaiting | rating_awaiting
    session_state: str

    # Previous session state — used by "رجوع" to navigate back intelligently
    prev_session_state: str

    # True after the welcome message has been shown in this session
    greeted: bool

    # Temporary data for multi-step after-sales flows (order ID, service type)
    after_sales_data: Optional[dict]