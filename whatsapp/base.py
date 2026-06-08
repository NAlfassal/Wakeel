from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class IncomingMessage:
    """
    Normalised representation of an inbound WhatsApp message.
    Decouples the agent from any specific platform payload format.
    """
    from_number: str  # e.g. whatsapp:+966501234567
    body: str         # plain text content of the message
    raw: dict         # original webhook payload (for debugging)


class WhatsAppProvider(ABC):
    """
    Abstract Adapter — isolates the agent from the messaging platform.

    To add a new platform (e.g. Green API, Meta Cloud API):
      1. Create a new class that inherits from WhatsAppProvider.
      2. Implement the three abstract methods.
      3. In main.py change: whatsapp = NewAdapter()
    """

    @abstractmethod
    def parse_incoming(self, payload: dict) -> IncomingMessage:
        """Convert raw webhook payload into a normalised IncomingMessage."""
        pass

    @abstractmethod
    def send_text(self, to: str, message: str) -> None:
        """Send a plain text message to a WhatsApp number."""
        pass

    @abstractmethod
    def send_list(self, to: str, header: str, body: str,
                  sections: list[dict]) -> None:
        """
        Send an interactive list message.

        sections format:
        [
          {
            "title": "Section label",
            "items": [
              {"id": "1", "title": "Option 1", "description": "Details"}
            ]
          }
        ]
        """
        pass