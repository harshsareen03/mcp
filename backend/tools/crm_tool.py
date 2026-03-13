from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import Customer, Order


class CRMTool:
    """Connector for CRM-style customer lookups."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_customer_details(self, customer_id: int) -> dict:
        customer = self.session.get(Customer, customer_id)
        if customer is None:
            raise LookupError(f"Customer {customer_id} was not found.")

        recent_orders = (
            self.session.query(Order)
            .filter(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .limit(5)
            .all()
        )

        return {
            "customer_id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "tier": customer.tier,
            "recent_orders": [
                {
                    "order_id": order.id,
                    "item_name": order.item_name,
                    "status": order.status,
                    "estimated_delivery": order.estimated_delivery,
                }
                for order in recent_orders
            ],
        }
