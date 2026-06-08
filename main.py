import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage

from agent import agent_graph, AgentState
from whatsapp import TwilioAdapter, IncomingMessage

app = FastAPI(title="WhatsApp AI Agent 🤖", version="1.0.0")

# Messaging provider — change this one line to switch platforms
whatsapp = TwilioAdapter()

# In-memory conversation and session storage (demo only)
# Production: replace with Redis
conversation_memory: dict[str, list] = {}
session_states:      dict[str, dict] = {}


@app.get("/")
async def root():
    return {
        "status": "✅ WhatsApp AI Agent is running",
        "store":   os.getenv("STORE_NAME", "متجر نور"),
        "webhook": "/webhook",
        "docs":    "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    """
    Twilio sends a POST here whenever a WhatsApp message arrives.
    Configure this URL in Twilio Sandbox Settings.
    """
    form_data = await request.form()
    payload   = dict(form_data)

    # Parse incoming message into a normalised object
    incoming: IncomingMessage = whatsapp.parse_incoming(payload)
    user_phone   = incoming.from_number
    user_message = incoming.body

    if not user_message:
        return PlainTextResponse("", status_code=200)

    print(f"\n📱 Message from {user_phone}: {user_message}")

    # Retrieve conversation history and session state
    history        = conversation_memory.get(user_phone, [])
    session_memory = session_states.get(user_phone, {})

    # Append the new user message
    history.append(HumanMessage(content=user_message))

    # Build initial agent state
    initial_state: AgentState = {
        "messages":           history,
        "user_phone":         user_phone,
        "intent":             None,
        "reply_text":         None,
        "reply_type":         "text",
        "list_data":          None,
        "is_done":            False,
        "session_state":      session_memory.get("session_state",      "fresh"),
        "prev_session_state": session_memory.get("prev_session_state", "menu"),
        "greeted":            session_memory.get("greeted",            False),
        "after_sales_data":   session_memory.get("after_sales_data",   None),
    }

    # Run the agent
    result = agent_graph.invoke(initial_state)

    # Persist conversation (last 20 messages) and session state
    conversation_memory[user_phone] = result["messages"][-20:]
    session_states[user_phone] = {
        "session_state":      result.get("session_state",      "menu"),
        "prev_session_state": result.get("prev_session_state", "menu"),
        "greeted":            result.get("greeted",            False),
        "after_sales_data":   result.get("after_sales_data",   None),
    }

    # Send the reply
    reply_type = result.get("reply_type", "text")
    reply_text = result.get("reply_text")
    list_data  = result.get("list_data")

    # ── DEBUG MODE: print to terminal instead of sending ──────────────
    # Set DEBUG_MODE=true in .env to test without hitting Twilio limits
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

    if DEBUG_MODE:
        print("\n" + "─" * 50)
        if reply_type == "list" and list_data:
            print(f"📋 LIST REPLY — {list_data['header']}")
            print(f"   {list_data['body']}")
            for s in list_data["sections"]:
                for item in s["items"]:
                    print(f"   {item['id']}. {item['title']}")
        elif reply_text:
            print(f"💬 TEXT REPLY:\n{reply_text}")
        print(f"🔖 session_state: {result.get('session_state', '?')}")
        print("─" * 50)
    else:
        if reply_type == "list" and list_data:
            whatsapp.send_list(
                to=user_phone,
                header=list_data["header"],
                body=list_data["body"],
                sections=list_data["sections"],
            )
            print(f"📤 Sent list: {list_data['header']}")
        elif reply_text:
            whatsapp.send_text(to=user_phone, message=reply_text)
            print(f"📤 Sent: {reply_text[:80]}...")

    return PlainTextResponse("", status_code=200)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Server running at: http://localhost:{port}")
    print(f"📋 Swagger Docs:      http://localhost:{port}/docs")
    print(f"🔗 Webhook URL:       http://localhost:{port}/webhook\n")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)