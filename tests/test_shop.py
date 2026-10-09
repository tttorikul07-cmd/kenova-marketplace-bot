from decimal import Decimal
import pytest
from app.database.models import Category, Product, LedgerEntry, Deposit, User
from app.services.shop import register_user, create_deposit, approve_deposit, reject_deposit, purchase_product, ShopError

def test_register_user_is_idempotent(db_session):
    a = register_user(db_session, 101, "alice", "Alice")
    b = register_user(db_session, 101, "alice_new", "Alice Updated")
    assert a.id == b.id
    assert b.username == "alice_new"
    assert db_session.query(User).count() == 1

def test_deposit_approval_credits_once(db_session):
    user = register_user(db_session, 202, None, "Bob")
    deposit = create_deposit(db_session, user, Decimal("50.00"), "bKash", "TXN123")
    approve_deposit(db_session, deposit.id, 999)
    assert Decimal(user.balance) == Decimal("50.00")
    assert db_session.query(LedgerEntry).count() == 1
    with pytest.raises(ShopError):
        approve_deposit(db_session, deposit.id, 999)
    assert Decimal(user.balance) == Decimal("50.00")
    assert db_session.query(LedgerEntry).count() == 1

def test_rejected_deposit_cannot_be_approved(db_session):
    user = register_user(db_session, 303, None, "Carol")
    dep = create_deposit(db_session, user, Decimal("30"), "Nagad", "TXN456")
    reject_deposit(db_session, dep.id, 999)
    with pytest.raises(ShopError):
        approve_deposit(db_session, dep.id, 999)
    assert Decimal(user.balance) == Decimal("0.00")

def test_purchase_deducts_balance_and_stock(db_session):
    user = register_user(db_session, 404, None, "Dara")
    user.balance = Decimal("100.00")
    category = Category(name="VPN")
    db_session.add(category); db_session.commit()
    product = Product(name="Authorized VPN plan", category_id=category.id, description="Test", price=Decimal("40.00"), active=True, stock=2)
    db_session.add(product); db_session.commit()
    order = purchase_product(db_session, user.id, product.id, 2)
    assert Decimal(order.total) == Decimal("80.00")
    assert Decimal(user.balance) == Decimal("20.00")
    assert product.stock == 0
    assert db_session.query(LedgerEntry).count() == 1

def test_purchase_rejects_insufficient_balance(db_session):
    user = register_user(db_session, 505, None, "Eli")
    category = Category(name="Proxy")
    db_session.add(category); db_session.commit()
    product = Product(name="Proxy plan", category_id=category.id, description="Test", price=Decimal("10.00"), active=True, stock=1)
    db_session.add(product); db_session.commit()
    with pytest.raises(ShopError, match="Insufficient balance"):
        purchase_product(db_session, user.id, product.id)
    assert product.stock == 1
