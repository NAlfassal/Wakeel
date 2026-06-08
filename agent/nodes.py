import os
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from .state import AgentState
from .prompts import RAG_PROMPT
from tools import (
    search_order, get_categories,
    get_products_by_category, format_product_list,
    search_knowledge
)

STORE_NAME = os.getenv("STORE_NAME", "متجر نور")

# ── Navigation keywords ──────────────────────────────────────────────
# "رجوع" = go back to the previous menu
# "قائمة" / "عودة" = go to the main menu from anywhere
BACK_TO_PREV    = "رجوع"
BACK_TO_MAIN    = ["قائمة", "عودة", "back", "menu", "الرئيسية"]

# ── End conversation keywords ───────────────────────────────────────
FAREWELL_WORDS  = ["انهاء", "إنهاء", "خروج", "وداع", "end", "bye", "exit", "goodbye"]

# ── Greeting keywords ────────────────────────────────────────────────
GREETING_WORDS  = ["مرحبا", "هلا", "السلام", "hi", "hello", "أهلا",
                   "اهلا", "صباح الخير", "مساء الخير", "هاي", "hey"]

# ── Sessions that accept free text input (awaiting user data) ────────
AWAITING_SESSIONS = [
    "warranty_awaiting", "return_awaiting", "exchange_awaiting",
    "maintenance_awaiting", "complaint_awaiting", "orders",
    "rating_awaiting"
]


def _get_llm():
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-lite-001"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.2,
        max_tokens=512,
    )


def _nav_footer() -> str:
    """Standard navigation hint shown at end of replies."""
    return "\n\n_(اكتب *رجوع* للقائمة السابقة | *قائمة* للرئيسية)_"


# ─────────────────────────────────────────────────────────────────────
# NODE 1: intent_node
# Decides which node to route to based on message + session_state.
# Core rule: free text is only processed in "policy" session.
# All other sessions require number selection.
# ─────────────────────────────────────────────────────────────────────
def intent_node(state: AgentState) -> AgentState:
    last_msg = state["messages"][-1].content if state["messages"] else ""
    lower    = last_msg.lower().strip()
    session  = state.get("session_state", "fresh")

    # ── 1. Navigation: رجوع → go back to previous menu ──────────────
    if lower == BACK_TO_PREV:
        prev = state.get("prev_session_state", "menu")
        # From awaiting sub-states → go back to after_sales menu
        if session in AWAITING_SESSIONS:
            return {**state, "intent": "after_sales_menu",
                    "session_state": "after_sales",
                    "prev_session_state": "menu",
                    "after_sales_data": None}
        prev_to_intent = {
            "after_sales": "after_sales_menu",
            "products":    "browse_products",
            "policy":      "faq",
            "menu":        "greeting",
        }
        return {**state, "intent": prev_to_intent.get(prev, "greeting"),
                "session_state": prev, "after_sales_data": None}

    # ── 2. Navigation: قائمة/عودة → go to main menu ─────────────────
    if any(w in lower for w in BACK_TO_MAIN):
        return {**state, "intent": "greeting",
                "session_state": "menu",
                "prev_session_state": state.get("session_state", "menu"),
                "after_sales_data": None}

    # ── 3. Greeting ──────────────────────────────────────────────────
    if any(w in lower for w in GREETING_WORDS):
        return {**state, "intent": "greeting"}

    # ── 3b. Farewell / End conversation ──────────────────────────────
    if any(w in lower for w in FAREWELL_WORDS):
        return {**state, "intent": "farewell"}

    # ── 3c. Rating response (1-5 while in rating_awaiting) ───────────
    if session == "rating_awaiting" and last_msg.strip() in ["1","2","3","4","5"]:
        return {**state, "intent": "rating"}

    # ── 4. Pass-through for awaiting sessions (expecting free text) ──
    if session in AWAITING_SESSIONS:
        mapping = {
            "warranty_awaiting":    "warranty",
            "return_awaiting":      "return_product",
            "exchange_awaiting":    "exchange_product",
            "maintenance_awaiting": "maintenance",
            "complaint_awaiting":   "complaint",
            "orders":               "track_order",
        }
        return {**state, "intent": mapping[session]}

    # ── 5. Number selection — context-aware ──────────────────────────
    if last_msg.strip() in ["1", "2", "3", "4", "5", "6"]:
        num = last_msg.strip()

        if session in ("menu", "fresh"):
            menu_map = {
                "1": "browse_products",
                "2": "track_order",
                "3": "faq",
                "4": "after_sales_menu",
                "5": "human_agent",
                "6": "farewell",
            }
            return {**state, "intent": menu_map.get(num, "prompt_menu")}

        if session == "products":
            return {**state, "intent": "browse_products"}

        if session == "after_sales":
            after_map = {
                "1": "return_product",
                "2": "exchange_product",
                "3": "maintenance",
                "4": "complaint",
            }
            return {**state, "intent": after_map.get(num, "after_sales_menu")}

        # Number received but session doesn't handle it → prompt
        return {**state, "intent": "prompt_menu"}

    # ── 6. Free text in "policy" session → allow RAG ─────────────────
    if session == "policy":
        return {**state, "intent": "faq"}

    # ── 7. All other free text → prompt user to select a number ──────
    return {**state, "intent": "prompt_menu"}


# ─────────────────────────────────────────────────────────────────────
# NODE 2: prompt_menu_node
# Shown when user sends free text outside of policy session.
# ─────────────────────────────────────────────────────────────────────
def prompt_menu_node(state: AgentState) -> AgentState:
    session = state.get("session_state", "menu")

    # Context-aware prompt based on current session
    if session == "after_sales":
        text = (
            "من فضلك اختر رقم الخدمة 👇\n\n"
            "1️⃣ 🔄 استرجاع منتج\n"
            "2️⃣ 🔁 استبدال منتج\n"
            "3️⃣ 🔨 طلب صيانة\n"
            "4️⃣ 📣 تقديم شكوى"
        )
    elif session == "products":
        categories = get_categories()
        lines = "\n".join(
            f"{i+1}️⃣ 📂 {cat}" for i, cat in enumerate(categories)
        )
        text = f"من فضلك اختر رقم الفئة 👇\n\n{lines}"
    else:
        text = (
            "من فضلك اختر رقم الخدمة من القائمة 👇\n\n"
            "1️⃣ 🛍️ تصفح المنتجات\n"
            "2️⃣ 📦 تتبع طلبي\n"
            "3️⃣ ❓ سياسات المتجر\n"
            "4️⃣ 🔧 خدمات ما بعد البيع\n"
            "5️⃣ 👨‍💼 موظف خدمة عملاء\n"
            "6️⃣ 👋 إنهاء المحادثة"
        )

    return {**state, "reply_type": "text", "reply_text": text}


# ─────────────────────────────────────────────────────────────────────
# NODE 3: greeting_node
# Shows main menu. Greeted flag ensures welcome shown only once.
# ─────────────────────────────────────────────────────────────────────
def greeting_node(state: AgentState) -> AgentState:
    list_data = {
        "header": f"👋 أهلاً بك! أنا وكيل، مساعدك الذكي في {STORE_NAME} 🤖",
        "body": "كيف أقدر أساعدك اليوم؟",
        "sections": [{"title": "الخدمات المتاحة", "items": [
            {"id": "1", "title": "🛍️ تصفح المنتجات",      "description": "اكتشف أحدث منتجاتنا"},
            {"id": "2", "title": "📦 تتبع طلبي",           "description": "تحقق من حالة طلبك"},
            {"id": "3", "title": "❓ سياسات المتجر",       "description": "إرجاع، شحن، دفع، ضمان"},
            {"id": "4", "title": "🔧 خدمات ما بعد البيع", "description": "استرجاع، استبدال، صيانة، شكاوى"},
            {"id": "5", "title": "👨‍💼 موظف خدمة عملاء",   "description": "تحدث مع موظفنا مباشرة"},
            {"id": "6", "title": "👋 إنهاء المحادثة",      "description": "تقييم الخدمة والمغادرة"},
        ]}]
    }
    return {
        **state,
        "reply_type": "list",
        "list_data": list_data,
        "reply_text": None,
        "session_state": "menu",
        "prev_session_state": state.get("session_state", "menu"),
        "greeted": True,
    }


# ─────────────────────────────────────────────────────────────────────
# NODE 4: browse_products_node
# Lists product categories, then shows products for selected category.
# ─────────────────────────────────────────────────────────────────────
def browse_products_node(state: AgentState) -> AgentState:
    last_msg   = state["messages"][-1].content.strip()
    session    = state.get("session_state", "menu")
    categories = get_categories()
    cat_map    = {str(i + 1): cat for i, cat in enumerate(categories)}

    # User selected a category number
    if session == "products" and last_msg in cat_map:
        chosen   = cat_map[last_msg]
        products = get_products_by_category(chosen)
        text     = f"📂 *{chosen}*\n\n{format_product_list(products)}{_nav_footer()}"
        return {**state, "reply_type": "text", "reply_text": text,
                "session_state": "products", "prev_session_state": "menu"}

    # Show category list
    items = [{"id": str(i + 1), "title": f"📂 {cat}", "description": ""}
             for i, cat in enumerate(categories)]
    list_data = {
        "header": "🛍️ تصفح المنتجات",
        "body": "اختر الفئة:",
        "sections": [{"title": "الفئات", "items": items}]
    }
    return {**state, "reply_type": "list", "list_data": list_data,
            "reply_text": None, "session_state": "products", "prev_session_state": "menu"}


# ─────────────────────────────────────────────────────────────────────
# NODE 5: track_order_node
# Looks up an order by ID. Waits for ORD-xxxx input.
# ─────────────────────────────────────────────────────────────────────
def track_order_node(state: AgentState) -> AgentState:
    last_msg = state["messages"][-1].content.upper().strip()
    match    = re.search(r"ORD-\d+", last_msg)

    if match:
        order_id = match.group()
        order    = search_order(order_id)
        if order:
            emoji = {
                "تم التسليم": "✅", "قيد الشحن": "🚚",
                "تم الشحن":   "📦", "قيد المعالجة": "⏳"
            }.get(order["status"], "📋")
            text = (
                f"🔍 *تفاصيل الطلب {order_id}*\n\n"
                f"👤 {order['customer']}\n"
                f"📦 {order['product']}\n"
                f"{emoji} *{order['status']}*\n"
                f"📅 {order['date']}\n"
            )
            if "delivery_date" in order:
                text += f"✅ تسليم: {order['delivery_date']}\n"
            elif "expected_delivery" in order:
                text += f"📅 متوقع: {order['expected_delivery']}\n"
            text += f"🔖 `{order['tracking']}`{_nav_footer()}"
        else:
            text = f"⚠️ لم أجد طلباً بالرقم *{order_id}*. تأكد من الرقم وأعد المحاولة."
        return {**state, "reply_type": "text", "reply_text": text,
                "session_state": "orders", "prev_session_state": "menu"}

    # No order ID found → ask for it
    text = "📦 *تتبع طلبك*\n\nأرسل رقم طلبك من فضلك.\nمثال: `ORD-1001`"
    return {**state, "reply_type": "text", "reply_text": text,
            "session_state": "orders", "prev_session_state": "menu"}


# ─────────────────────────────────────────────────────────────────────
# NODE 6: faq_node
# Handles store policy questions using RAG only.
# Called when session = "policy" (number 3 selected from menu).
# ─────────────────────────────────────────────────────────────────────
def faq_node(state: AgentState) -> AgentState:
    query   = state["messages"][-1].content.strip()
    session = state.get("session_state", "menu")

    # First visit (number 3 from main menu) → show welcome prompt
    if query == "3" and session in ("menu", "fresh"):
        return {
            **state,
            "reply_type": "text",
            "reply_text": (
                "❓ *سياسات المتجر*\n\n"
                "كيف أستطيع خدمتك؟ 😊\n\n"
                "بإمكانك سؤالي عن:\n"
                "• سياسة الاسترجاع\n"
                "• سياسة الاستبدال\n"
                "• مدة التوصيل والشحن\n"
                "• خيارات الدفع\n"
                "• سياسة الضمان\n"
                "• برنامج نقاط الولاء\n\n"
                "اكتب سؤالك الآن 👇"
                + _nav_footer()
            ),
            "session_state": "policy",
            "prev_session_state": "menu",
        }

    # Search RAG knowledge base
    rag_context = search_knowledge(query)
    if rag_context:
        llm    = _get_llm()
        prompt = RAG_PROMPT.format(
            store_name=STORE_NAME,
            context=rag_context,
            question=query,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return {**state, "reply_type": "text",
                "reply_text": response.content + _nav_footer(),
                "session_state": "policy", "prev_session_state": "menu"}

    # RAG found nothing relevant
    return {**state, "reply_type": "text",
            "reply_text": (
                "عذراً، ما عندي معلومات كافية عن هذا الموضوع. 😔\n"
                "يمكنني الإجابة عن سياسات الإرجاع والشحن والضمان والدفع."
                + _nav_footer()
            ),
            "session_state": "policy", "prev_session_state": "menu"}


# ─────────────────────────────────────────────────────────────────────
# NODE 7: after_sales_menu_node
# Shows the after-sales services menu (return, exchange, maintenance, complaint).
# ─────────────────────────────────────────────────────────────────────
def after_sales_menu_node(state: AgentState) -> AgentState:
    list_data = {
        "header": "🔧 خدمات ما بعد البيع",
        "body": "اختر نوع طلبك:",
        "sections": [{"title": "الخدمات", "items": [
            {"id": "1", "title": "🔄 استرجاع منتج",  "description": "استرداد المبلغ خلال 14 يوم"},
            {"id": "2", "title": "🔁 استبدال منتج",  "description": "عيب مصنعي خلال 7 أيام"},
            {"id": "3", "title": "🔨 طلب صيانة",     "description": "إصلاح المنتج مع فحص الضمان"},
            {"id": "4", "title": "📣 تقديم شكوى",    "description": "شكوى عن الخدمة أو التوصيل"},
        ]}]
    }
    return {**state, "reply_type": "list", "list_data": list_data,
            "reply_text": None, "session_state": "after_sales", "prev_session_state": "menu"}


# ─────────────────────────────────────────────────────────────────────
# NODE 8: human_agent_node
# Escalates the conversation to a human agent.
# ─────────────────────────────────────────────────────────────────────
def human_agent_node(state: AgentState) -> AgentState:
    text = (
        "👨‍💼 *تحويل لموظف خدمة العملاء*\n\n"
        "تم تسجيل طلبك ✅\n"
        "سيتواصل معك أحد موظفينا خلال *دقائق* 🕐\n\n"
        "أوقات العمل: السبت - الخميس | 9ص - 9م\n\n"
        f"شكراً لتواصلك مع *{STORE_NAME}* 💙"
    )
    return {**state, "reply_type": "text", "reply_text": text,
            "is_done": True, "session_state": "menu"}


# ─────────────────────────────────────────────────────────────────────
# NODE: farewell_node
# Triggered when user wants to end the conversation.
# Asks for a service rating before closing.
# ─────────────────────────────────────────────────────────────────────
def farewell_node(state: AgentState) -> AgentState:
    list_data = {
        "header": "شكراً لتواصلك معنا! 😊",
        "body": "الرجاء تقييم تجربتك مع خدمة العملاء:",
        "sections": [{"title": "التقييم", "items": [
            {"id": "5", "title": "⭐⭐⭐⭐⭐  ممتاز",   "description": ""},
            {"id": "4", "title": "⭐⭐⭐⭐    جيد جداً", "description": ""},
            {"id": "3", "title": "⭐⭐⭐      جيد",      "description": ""},
            {"id": "2", "title": "⭐⭐        مقبول",    "description": ""},
            {"id": "1", "title": "⭐          ضعيف",    "description": ""},
        ]}]
    }
    return {
        **state,
        "reply_type":         "list",
        "list_data":          list_data,
        "reply_text":         None,
        "session_state":      "rating_awaiting",
        "prev_session_state": state.get("session_state", "menu"),
    }


# ─────────────────────────────────────────────────────────────────────
# NODE: rating_node
# Receives the customer's rating (1-5) and closes the session.
# ─────────────────────────────────────────────────────────────────────
def rating_node(state: AgentState) -> AgentState:
    rating = state["messages"][-1].content.strip()

    rating_messages = {
        "5": "⭐⭐⭐⭐⭐ شكراً جزيلاً على تقييمك الرائع! 🙏\nسعداء بخدمتك دائماً.",
        "4": "⭐⭐⭐⭐ شكراً على تقييمك! 🙏\nسنسعى دائماً لتقديم الأفضل.",
        "3": "⭐⭐⭐ شكراً على ملاحظتك! 🙏\nسنعمل على تحسين خدمتنا.",
        "2": "⭐⭐ شكراً على صراحتك! 🙏\nنأسف لتجربتك وسنتواصل معك قريباً.",
        "1": "⭐ نأسف جداً على تجربتك! 🙏\nسيتواصل معك مشرف خدمة العملاء قريباً.",
    }

    reply = rating_messages.get(rating, "شكراً على تقييمك! 🙏")
    reply += f"\n\nنتطلع لخدمتك مجدداً في *{STORE_NAME}* 💙"

    return {
        **state,
        "reply_type":         "text",
        "reply_text":         reply,
        "session_state":      "fresh",  # Reset session after rating
        "prev_session_state": "menu",
        "greeted":            False,    # Show welcome again next time
        "is_done":            True,
        "after_sales_data":   None,
    }