from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import Customer, SupportTicket


class TicketTool:
    """Connector for support ticket creation."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_support_ticket(self, customer_id: int, issue: str) -> dict:
        customer = self.session.get(Customer, customer_id)
        if customer is None:
            raise LookupError(f"Customer {customer_id} was not found.")
        if not issue.strip():
            raise ValueError("Issue description cannot be empty.")

        priority = "high" if any(word in issue.lower() for word in ["refund", "angry", "cancel", "damaged"]) else "normal"
        ticket = SupportTicket(
            customer_id=customer_id,
            issue=issue.strip(),
            status="open",
            priority=priority,
            summary=issue.strip()[:240],
        )
        self.session.add(ticket)
        self.session.commit()
        self.session.refresh(ticket)

        return {
            "ticket_id": ticket.id,
            "customer_id": ticket.customer_id,
            "status": ticket.status,
            "priority": ticket.priority,
            "summary": ticket.summary,
            "created_at": ticket.created_at.isoformat(),
        }
