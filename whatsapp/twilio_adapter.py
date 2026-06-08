import os
from twilio.rest import Client
from .base import WhatsAppProvider, IncomingMessage


class TwilioAdapter(WhatsAppProvider):
    """
    WhatsAppProvider implementation using Twilio.
    To switch platforms, replace this file only — the agent is unaffected.
    """

    def __init__(self):
        self.client      = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
        self.from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")

    def parse_incoming(self, payload: dict) -> IncomingMessage:
        """Extract sender number and message body from Twilio webhook payload."""
        return IncomingMessage(
            from_number=payload.get("From", ""),
            body=payload.get("Body", "").strip(),
            raw=payload,
        )

    def send_text(self, to: str, message: str) -> None:
        """Send a plain text WhatsApp message via Twilio."""
        self.client.messages.create(
            from_=self.from_number,
            to=to,
            body=message,
        )

    def send_list(self, to: str, header: str, body: str,
                  sections: list[dict]) -> None:
        """
        Render an interactive list as formatted text.

        Note: Twilio Sandbox does not fully support WhatsApp Interactive
        Messages. For production, migrate to Twilio Content API or a
        platform that supports native list messages (e.g. 360Dialog).
        """
        text = f"*{header}*\n{body}\n\n"
        for section in sections:
            if section.get("title"):
                text += f"📂 *{section['title']}*\n"
            for item in section.get("items", []):
                text += f"  {item['id']}️⃣ {item['title']}"
                if item.get("description"):
                    text += f"\n     _{item['description']}_"
                text += "\n"
        text += "\nاكتب رقم اختيارك 👆"
        self.send_text(to, text)