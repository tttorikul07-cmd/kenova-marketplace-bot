from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import User, Product, Deposit, Order, LedgerEntry

class ShopError(Exception):
    pass

def register_user(session: Session, telegram_id: int, username: str | None, first_name: str) -> User:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        user.username = username
        user.first_name = (first_name or "Customer")[:128]
    else:
        user = User(telegram_id=telegram_id, username=username, first_name=(first_name or "Customer")[:128])
        session.add(user)
    session.commit()
    return user

def create_deposit(session: Session, user: User, amount: Decimal, method: str, payment_reference: str) -> Deposit:
    if amount <= 0:
        raise ShopError("Amount must be greater than zero.")
    if method not in {"bKash", "Nagad", "Rocket"}:
        raise ShopError("Unsupported payment method.")
    payment_reference = payment_reference.strip()
    if not payment_reference or len(payment_reference) > 120:
        raise ShopError("Enter a valid payment reference.")
    deposit = Deposit(reference=f"DEP-{uuid4().hex[:12].upper()}", user_id=user.id, amount=amount,
                      method=method, payment_reference=payment_reference)
    session.add(deposit)
    session.commit()
    return deposit

def approve_deposit(session: Session, deposit_id: int, admin_telegram_id: int) -> Deposit:
    deposit = session.scalar(select(Deposit).where(Deposit.id == deposit_id).with_for_update())
    if not deposit:
        raise ShopError("Deposit not found.")
    if deposit.status != "pending":
        raise ShopError("This deposit has already been reviewed.")
    user = session.scalar(select(User).where(User.id == deposit.user_id).with_for_update())
    if not user:
        raise ShopError("Customer not found.")
    deposit.status = "approved"
    deposit.reviewed_by = admin_telegram_id
    deposit.reviewed_at = datetime.now(timezone.utc)
    user.balance = Decimal(user.balance) + Decimal(deposit.amount)
    session.add(LedgerEntry(user_id=user.id, amount=Decimal(deposit.amount), entry_type="deposit",
                            reference=deposit.reference, note=f"Approved {deposit.method} deposit"))
    session.commit()
    return deposit

def reject_deposit(session: Session, deposit_id: int, admin_telegram_id: int) -> Deposit:
    deposit = session.get(Deposit, deposit_id)
    if not deposit:
        raise ShopError("Deposit not found.")
    if deposit.status != "pending":
        raise ShopError("This deposit has already been reviewed.")
    deposit.status = "rejected"
    deposit.reviewed_by = admin_telegram_id
    deposit.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    return deposit

def purchase_product(session: Session, user_id: int, product_id: int, quantity: int = 1) -> Order:
    if quantity < 1 or quantity > 20:
        raise ShopError("Quantity must be between 1 and 20.")
    # SQLite's write transaction is serialized by the database; production should use PostgreSQL.
    product = session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        raise ShopError("Customer not found.")
    if not product or not product.active:
        raise ShopError("This product is not available.")
    if product.stock is not None and product.stock < quantity:
        raise ShopError("Not enough stock available.")
    total = Decimal(product.price) * quantity
    if Decimal(user.balance) < total:
        raise ShopError("Insufficient balance. Please deposit funds first.")
    user.balance = Decimal(user.balance) - total
    if product.stock is not None:
        product.stock -= quantity
    order_number = f"KN-{uuid4().hex[:10].upper()}"
    order = Order(order_number=order_number, user_id=user.id, product_id=product.id,
                  product_name=product.name, quantity=quantity, unit_price=Decimal(product.price),
                  total=total, payment_status="paid", status="pending")
    session.add(order)
    session.add(LedgerEntry(user_id=user.id, amount=-total, entry_type="purchase",
                            reference=order_number, note=f"Purchase {product.name}"))
    session.commit()
    return order
