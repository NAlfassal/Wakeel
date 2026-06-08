import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def get_products() -> list:
    """Load all products from products.json."""
    with open(DATA_DIR / "products.json", encoding="utf-8") as f:
        return json.load(f)


def search_order(order_id: str) -> dict | None:
    """Look up a single order by ID. Returns None if not found."""
    with open(DATA_DIR / "orders.json", encoding="utf-8") as f:
        orders = json.load(f)
    return orders.get(order_id.upper().strip())


def get_categories() -> list[str]:
    """Return a deduplicated list of product categories."""
    return list(set(p["category"] for p in get_products()))


def get_products_by_category(category: str) -> list:
    """Return all products belonging to the given category."""
    return [p for p in get_products() if p["category"] == category]


def format_product_list(products: list) -> str:
    """Format a list of products into a WhatsApp-friendly string."""
    lines = []
    for p in products:
        stock = "✅ متوفر" if p["in_stock"] else "❌ نفذ المخزون"
        lines.append(f"*{p['name']}*\n💰 {p['price']} {p['currency']} | {stock}")
    return "\n\n".join(lines)