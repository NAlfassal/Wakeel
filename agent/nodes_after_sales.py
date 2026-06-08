import os
import re
from datetime import datetime, timedelta
from .state import AgentState
from tools import search_order

STORE_NAME = os.getenv("STORE_NAME", "متجر نور")

# Warranty periods in days by product category
WARRANTY_DAYS = {
    "إلكترونيات":  365,  # 1 year
    "اكسسوارات":   180,  # 6 months
    "أثاث المكتب": 730,  # 2 years
}

RETURN_DAYS   = 14  # Days allowed for returns
EXCHANGE_DAYS = 7   # Days allowed for exchanges (manufacturing defect only)


def _nav_footer() -> str:
    """Standard navigation hint appended to all replies."""
    return "\n\n_(اكتب *رجوع* للقائمة السابقة | *قائمة* للرئيسية)_"


def _extract_order_id(text: str) -> str | None:
    """Extract ORD-xxxx from a message string."""
    match = re.search(r"ORD-\d+", text.upper())
    return match.group() if match else None


def _check_eligibility(order: dict, days: int) -> dict:
    """
    Generic eligibility checker for return, exchange, and warranty.
    Returns a dict with 'eligible', 'reason', and date fields.
    """
    if "delivery_date" not in order:
        return {
            "eligible": False,
            "reason":   "not_delivered",
            "status":   order.get("status", "غير معروف"),
        }
    delivery       = datetime.strptime(order["delivery_date"], "%Y-%m-%d")
    expiry         = delivery + timedelta(days=days)
    today          = datetime.now()
    days_remaining = (expiry - today).days
    return {
        "eligible":       today <= expiry,
        "reason":         "eligible" if today <= expiry else "expired",
        "delivery_date":  order["delivery_date"],
        "expiry_date":    expiry.strftime("%Y-%m-%d"),
        "days_remaining": days_remaining,
    }


def _order_lookup(state: AgentState, awaiting_session: str) -> tuple:
    """
    Shared helper: extract order ID from message and look up the order.
    Returns (order_id, order, error_state) where error_state is set if
    something went wrong and the caller should return it directly.
    """
    last_msg = state["messages"][-1].content
    order_id = _extract_order_id(last_msg)

    if not order_id:
        error = {**state, "reply_type": "text",
                 "reply_text": "⚠️ أرسل رقم الطلب مثل: `ORD-1001`",
                 "session_state": awaiting_session}
        return None, None, error

    order = search_order(order_id)
    if not order:
        error = {**state, "reply_type": "text",
                 "reply_text": f"⚠️ لم أجد طلباً بالرقم *{order_id}*. تأكد من الرقم.",
                 "session_state": awaiting_session}
        return order_id, None, error

    return order_id, order, None


# ─────────────────────────────────────────────────────────────────────
# NODE: return_node
# Handles product return requests. Validates 14-day return window.
# Step 1: Ask for order ID + reason.
# Step 2: Verify eligibility and create return ticket.
# ─────────────────────────────────────────────────────────────────────
def return_node(state: AgentState) -> AgentState:
    session = state.get("session_state", "menu")

    # Step 1: request order details
    if session != "return_awaiting":
        return {
            **state,
            "reply_type": "text",
            "reply_text": (
                "🔄 *طلب استرجاع*\n\n"
                "من فضلك أرسل:\n"
                "• رقم الطلب (مثال: ORD-1001)\n"
                "• سبب الاسترجاع\n\n"
                "_الاسترجاع متاح خلال 14 يوم من تاريخ الاستلام_"
                + _nav_footer()
            ),
            "session_state":      "return_awaiting",
            "prev_session_state": "after_sales",
            "after_sales_data":   {"type": "return"},
        }

    # Step 2: process the reply
    order_id, order, err = _order_lookup(state, "return_awaiting")
    if err:
        return err

    result = _check_eligibility(order, RETURN_DAYS)

    if result["reason"] == "not_delivered":
        text = (
            f"⚠️ *لا يمكن طلب الاسترجاع*\n\n"
            f"📦 المنتج: {order['product']}\n"
            f"🚚 حالة الطلب: *{result['status']}*\n\n"
            f"الاسترجاع متاح فقط بعد استلام المنتج."
            + _nav_footer()
        )
    elif result["eligible"]:
        text = (
            f"⏳ *جاري التحقق من أهلية الاسترجاع...*\n\n"
            f"✅ *المنتج مؤهل للاسترجاع*\n\n"
            f"📦 المنتج: {order['product']}\n"
            f"📅 تاريخ الاستلام: {result['delivery_date']}\n"
            f"⏰ المتبقي من فترة الاسترجاع: {result['days_remaining']} يوم\n\n"
            f"✅ *تم تسجيل طلب الاسترجاع*\n"
            f"سيتواصل معك فريقنا خلال 24 ساعة لترتيب الاستلام 📦\n\n"
            f"رقم الطلب: *RET-{order_id[4:]}*"
            + _nav_footer()
        )
    else:
        text = (
            f"⏳ *جاري التحقق...*\n\n"
            f"❌ *انتهت فترة الاسترجاع (14 يوم)*\n\n"
            f"📅 تاريخ الاستلام: {result['delivery_date']}\n"
            f"📆 انتهت الفترة في: {result['expiry_date']}"
            + _nav_footer()
        )

    return {**state, "reply_type": "text", "reply_text": text,
            "session_state": "after_sales", "prev_session_state": "menu",
            "after_sales_data": None}


# ─────────────────────────────────────────────────────────────────────
# NODE: exchange_node
# Handles product exchange requests. Validates 7-day exchange window.
# ─────────────────────────────────────────────────────────────────────
def exchange_node(state: AgentState) -> AgentState:
    session = state.get("session_state", "menu")

    # Step 1: request order details
    if session != "exchange_awaiting":
        return {
            **state,
            "reply_type": "text",
            "reply_text": (
                "🔁 *طلب استبدال*\n\n"
                "من فضلك أرسل:\n"
                "• رقم الطلب (مثال: ORD-1001)\n"
                "• وصف العيب المصنعي\n\n"
                "_الاستبدال متاح خلال 7 أيام من الاستلام للعيوب المصنعية فقط_"
                + _nav_footer()
            ),
            "session_state":      "exchange_awaiting",
            "prev_session_state": "after_sales",
            "after_sales_data":   {"type": "exchange"},
        }

    # Step 2: process the reply
    order_id, order, err = _order_lookup(state, "exchange_awaiting")
    if err:
        return err

    result = _check_eligibility(order, EXCHANGE_DAYS)

    if result["reason"] == "not_delivered":
        text = (
            f"⚠️ *لا يمكن طلب الاستبدال*\n\n"
            f"📦 المنتج: {order['product']}\n"
            f"🚚 حالة الطلب: *{result['status']}*\n\n"
            f"الاستبدال متاح فقط بعد استلام المنتج."
            + _nav_footer()
        )
    elif result["eligible"]:
        text = (
            f"⏳ *جاري التحقق من أهلية الاستبدال...*\n\n"
            f"✅ *المنتج مؤهل للاستبدال*\n\n"
            f"📦 المنتج: {order['product']}\n"
            f"📅 تاريخ الاستلام: {result['delivery_date']}\n"
            f"⏰ المتبقي: {result['days_remaining']} يوم\n\n"
            f"✅ *تم تسجيل طلب الاستبدال*\n"
            f"سيتواصل معك فريقنا خلال 24 ساعة لترتيب الاستلام والبديل 🔁\n\n"
            f"رقم الطلب: *EXC-{order_id[4:]}*"
            + _nav_footer()
        )
    else:
        text = (
            f"⏳ *جاري التحقق...*\n\n"
            f"❌ *انتهت فترة الاستبدال (7 أيام)*\n\n"
            f"📅 تاريخ الاستلام: {result['delivery_date']}\n"
            f"📆 انتهت الفترة في: {result['expiry_date']}\n\n"
            f"يمكنك طلب *الصيانة* بدلاً من ذلك — اختر 3 من القائمة."
            + _nav_footer()
        )

    return {**state, "reply_type": "text", "reply_text": text,
            "session_state": "after_sales", "prev_session_state": "menu",
            "after_sales_data": None}


# ─────────────────────────────────────────────────────────────────────
# NODE: maintenance_node
# Handles maintenance requests. Auto-checks warranty to determine
# whether service is free (under warranty) or paid.
# ─────────────────────────────────────────────────────────────────────
def maintenance_node(state: AgentState) -> AgentState:
    session = state.get("session_state", "menu")

    # Step 1: request order details
    if session != "maintenance_awaiting":
        return {
            **state,
            "reply_type": "text",
            "reply_text": (
                "🔨 *طلب صيانة*\n\n"
                "من فضلك أرسل:\n"
                "• رقم الطلب (مثال: ORD-1001)\n"
                "• وصف العطل\n\n"
                "_سنتحقق تلقائياً من حالة الضمان_"
                + _nav_footer()
            ),
            "session_state":      "maintenance_awaiting",
            "prev_session_state": "after_sales",
            "after_sales_data":   {"type": "maintenance"},
        }

    # Step 2: process the reply
    order_id, order, err = _order_lookup(state, "maintenance_awaiting")
    if err:
        return err

    # Auto warranty check based on product category
    category     = order.get("category", "اكسسوارات")
    warranty_days = WARRANTY_DAYS.get(category, 180)
    result       = _check_eligibility(order, warranty_days)

    if result["reason"] == "not_delivered":
        text = (
            f"⚠️ *لا يمكن طلب الصيانة*\n\n"
            f"📦 المنتج: {order['product']}\n"
            f"🚚 حالة الطلب: *{result['status']}*"
            + _nav_footer()
        )
    elif result["eligible"]:
        text = (
            f"⏳ *جاري التحقق من حالة الضمان...*\n\n"
            f"✅ *المنتج مازال تحت الضمان — الصيانة مجانية*\n\n"
            f"📦 المنتج: {order['product']}\n"
            f"🛡️ الضمان ينتهي: {result['expiry_date']}\n"
            f"⏰ المتبقي: {result['days_remaining']} يوم\n\n"
            f"✅ *تم تسجيل طلب الصيانة*\n"
            f"سيتواصل معك فريقنا خلال 24 ساعة لترتيب الاستلام 🔧\n\n"
            f"رقم الطلب: *MNT-{order_id[4:]}*"
            + _nav_footer()
        )
    else:
        text = (
            f"⏳ *جاري التحقق من حالة الضمان...*\n\n"
            f"❌ *انتهى الضمان — الصيانة بتكلفة*\n\n"
            f"📦 المنتج: {order['product']}\n"
            f"📆 انتهى الضمان في: {result['expiry_date']}\n\n"
            f"✅ *تم تسجيل طلب الصيانة المدفوعة*\n"
            f"سيتواصل معك فريقنا خلال 24 ساعة لتحديد التكلفة 💰\n\n"
            f"رقم الطلب: *MNT-{order_id[4:]}*"
            + _nav_footer()
        )

    return {**state, "reply_type": "text", "reply_text": text,
            "session_state": "after_sales", "prev_session_state": "menu",
            "after_sales_data": None}


# ─────────────────────────────────────────────────────────────────────
# NODE: complaint_node
# Logs customer complaints. Step 1: show complaint type menu.
# Step 2: register the complaint and issue a reference number.
# ─────────────────────────────────────────────────────────────────────
def complaint_node(state: AgentState) -> AgentState:
    session  = state.get("session_state", "menu")
    last_msg = state["messages"][-1].content.strip()

    # Step 1: show complaint type selection
    if session != "complaint_awaiting":
        list_data = {
            "header": "📣 تقديم شكوى",
            "body":   "ما نوع الشكوى؟",
            "sections": [{"title": "نوع الشكوى", "items": [
                {"id": "1", "title": "🚚 شكوى توصيل", "description": "تأخر أو مشكلة في التوصيل"},
                {"id": "2", "title": "🛍️ شكوى منتج",  "description": "جودة أو مواصفات المنتج"},
                {"id": "3", "title": "👨‍💼 شكوى خدمة", "description": "مشكلة مع خدمة العملاء"},
                {"id": "4", "title": "📋 أخرى",        "description": "شكوى أخرى"},
            ]}]
        }
        return {
            **state,
            "reply_type":         "list",
            "list_data":          list_data,
            "session_state":      "complaint_awaiting",
            "prev_session_state": "after_sales",
            "after_sales_data":   {"type": "complaint"},
        }

    # Step 2: register the complaint
    types = {"1": "شكوى توصيل", "2": "شكوى منتج",
             "3": "شكوى خدمة",  "4": "شكوى أخرى"}
    complaint_type = types.get(last_msg, "شكوى عامة")
    ref_number     = f"CMP-{datetime.now().strftime('%d%m%H%M')}"

    text = (
        f"📣 *تسجيل شكوى — {complaint_type}*\n\n"
        f"✅ تم استلام شكواك وتسجيلها بنجاح\n\n"
        f"رقم الشكوى: *{ref_number}*\n\n"
        f"سيتواصل معك فريقنا خلال *24 ساعة* 📞\n\n"
        f"شكراً لمساعدتنا في التحسين 🙏"
        + _nav_footer()
    )

    return {**state, "reply_type": "text", "reply_text": text,
            "session_state": "after_sales", "prev_session_state": "menu",
            "after_sales_data": None}


# ─────────────────────────────────────────────────────────────────────
# NOTE: warranty_node is kept for backward compatibility but
# warranty checking is now handled automatically inside maintenance_node.
# ─────────────────────────────────────────────────────────────────────
def warranty_node(state: AgentState) -> AgentState:
    """Redirect warranty requests to maintenance_node."""
    return maintenance_node(state)