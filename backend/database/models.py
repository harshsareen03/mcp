from __future__ import annotations

from datetime import datetime, timedelta
from typing import Generator

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(50), default="")
    tier: Mapped[str] = mapped_column(String(50), default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    tickets: Mapped[list["SupportTicket"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(80), default="")
    shipping_carrier: Mapped[str] = mapped_column(String(80), default="")
    estimated_delivery: Mapped[str] = mapped_column(String(80), default="")
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open")
    priority: Mapped[str] = mapped_column(String(50), default="normal")
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="tickets")


DATABASE_URL = "sqlite:///./support_agent.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_example_data() -> None:
    session = SessionLocal()
    try:
        if session.query(Customer).count() > 0:
            return

        customer_1 = Customer(
            id=1,
            name="Alice Johnson",
            email="alice@example.com",
            phone="+1-415-555-0101",
            tier="gold",
        )
        customer_2 = Customer(
            id=2,
            name="Marco Rivera",
            email="marco@example.com",
            phone="+1-415-555-0102",
            tier="standard",
        )

        order_1 = Order(
            id=45231,
            customer_id=1,
            status="shipped",
            item_name="Noise-Cancelling Headphones",
            tracking_number="ZX991245US",
            shipping_carrier="FedEx",
            estimated_delivery=(datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
            total_amount=199.99,
        )
        order_2 = Order(
            id=45232,
            customer_id=1,
            status="processing",
            item_name="Wireless Mouse",
            tracking_number="",
            shipping_carrier="",
            estimated_delivery=(datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%d"),
            total_amount=59.99,
        )
        order_3 = Order(
            id=55210,
            customer_id=2,
            status="delivered",
            item_name="4K Monitor",
            tracking_number="TRK2048840",
            shipping_carrier="UPS",
            estimated_delivery=(datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
            total_amount=429.00,
        )

        ticket = SupportTicket(
            customer_id=2,
            issue="Monitor stand arrived scratched.",
            status="open",
            priority="normal",
            summary="Customer reported cosmetic damage on delivery.",
        )

        session.add_all([customer_1, customer_2, order_1, order_2, order_3, ticket])
        session.commit()
    finally:
        session.close()
