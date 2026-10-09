"""Insert sample categories/products for local testing. Run: python -m scripts.seed_demo"""
from decimal import Decimal
from sqlalchemy import select
from app.database.session import SessionLocal, init_db
from app.database.models import Category, Product

SAMPLES = [
    ("VPN", "NordVPN 7 Days", "Authorized VPN subscription service, 7-day plan.", "40.00", None),
    ("VPN", "Proton VPN 7 Days", "Authorized VPN subscription service, 7-day plan.", "40.00", None),
    ("Proxy", "OWL Proxy Basic", "Authorized proxy service plan. Configure valid supplier fulfillment before selling.", "50.00", None),
]

def main():
    init_db()
    with SessionLocal() as db:
        for category_name, name, description, price, stock in SAMPLES:
            category = db.scalar(select(Category).where(Category.name == category_name))
            if not category:
                category = Category(name=category_name)
                db.add(category); db.flush()
            product = db.scalar(select(Product).where(Product.name == name))
            if not product:
                db.add(Product(name=name, category_id=category.id, description=description, price=Decimal(price), stock=stock, active=True))
        db.commit()
    print("Demo products are ready. Review pricing and supplier authorization before production.")

if __name__ == "__main__": main()
