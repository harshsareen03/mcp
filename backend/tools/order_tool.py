from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import Order


class OrderTool:
    """Connector for order database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_order_status(self, order_id: str) -> dict:
        try:
            numeric_order_id = int(str(order_id).replace("#", "").strip())
        except ValueError as exc:
            raise ValueError("Order ID must be numeric.") from exc

        order = self.session.get(Order, numeric_order_id)
        if order is None:
            raise LookupError(f"Order {numeric_order_id} was not found.")

        return {
            "order_id": order.id,
            "customer_id": order.customer_id,
            "item_name": order.item_name,
            "status": order.status,
            "tracking_number": order.tracking_number or "Not assigned yet",
            "shipping_carrier": order.shipping_carrier or "Not assigned yet",
            "estimated_delivery": order.estimated_delivery,
            "total_amount": order.total_amount,
        }
