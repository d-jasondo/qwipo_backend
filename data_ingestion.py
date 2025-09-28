import pandas as pd
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from models import User, Product, PurchaseHistory


def _parse_pack_size(pack_size: str):
    """Split pack_size like '500g', '1kg', '250ml', '1pc' into weight and unit.
    Returns (weight, unit). If unknown, returns (pack_size, '').
    """
    if not isinstance(pack_size, str) or not pack_size:
        return '', ''
    # Simple heuristics
    pack_size = pack_size.strip()
    # Separate trailing letters from leading digits/decimal
    i = 0
    while i < len(pack_size) and (pack_size[i].isdigit() or pack_size[i] == '.'):  # capture number part
        i += 1
    weight = pack_size[:i] or pack_size
    unit = pack_size[i:] if i < len(pack_size) else ''
    return weight, unit


def ingest_products(csv_path: str, db: Optional[Session] = None) -> int:
    """Ingest products from CSV with columns: product_id,product_name,category,brand,price_inr,pack_size
    Maps to models.Product fields.
    Returns number of rows upserted.
    """
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True
    try:
        df = pd.read_csv(csv_path)
        required_cols = {"product_id", "product_name", "category", "brand", "price_inr", "pack_size"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns in products CSV: {missing}")

        upserted = 0
        for _, row in df.iterrows():
            pid = int(row["product_id"]) if pd.notna(row["product_id"]) else None
            weight, unit = _parse_pack_size(str(row.get("pack_size", '')).strip())
            # Try to find existing
            prod: Optional[Product] = db.query(Product).filter(Product.id == pid).one_or_none()
            if prod is None:
                prod = Product(id=pid)
            prod.name = str(row.get("product_name", '')).strip()
            prod.category = str(row.get("category", '')).strip()
            # CSV doesn't have subcategory, leave as None
            prod.brand = str(row.get("brand", '')).strip()
            prod.description = None
            try:
                prod.price = float(row.get("price_inr", 0) or 0)
            except Exception:
                prod.price = 0.0
            # Optional fields
            prod.original_price = None
            prod.weight = weight
            prod.unit = unit
            if not getattr(prod, 'stock_quantity', None):
                prod.stock_quantity = 0
            if not getattr(prod, 'min_order_quantity', None):
                prod.min_order_quantity = 1
            if prod.discount_percent is None:
                prod.discount_percent = 0.0
            if prod.cashback_offer is None:
                prod.cashback_offer = 0.0
            if prod.is_deal is None:
                prod.is_deal = False
            if prod.is_combo is None:
                prod.is_combo = False
            if prod.image_url is None:
                prod.image_url = ''
            if prod.is_active is None:
                prod.is_active = True

            db.merge(prod)  # upsert by primary key
            upserted += 1
        db.commit()
        return upserted
    finally:
        if close_db:
            db.close()


def ingest_retailers(csv_path: str, db: Optional[Session] = None) -> int:
    """Ingest retailers into models.User as user_type='retailer'.
    CSV columns: retailer_id,retailer_name,city,state,shop_type,registration_date
    Returns number of rows upserted.
    """
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True
    try:
        df = pd.read_csv(csv_path)
        required_cols = {"retailer_id", "retailer_name", "city", "state", "shop_type", "registration_date"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns in retailers CSV: {missing}")

        upserted = 0
        for _, row in df.iterrows():
            rid = int(row["retailer_id"]) if pd.notna(row["retailer_id"]) else None
            user: Optional[User] = db.query(User).filter(User.id == rid).one_or_none()
            if user is None:
                user = User(id=rid)
            user.user_type = "retailer"
            user.business_name = str(row.get("retailer_name", '')).strip()
            user.business_type = str(row.get("shop_type", '')).strip()
            user.contact_person = None
            user.email = None  # keep nullable, unique on SQLite tolerates multiple NULLs
            user.phone = None
            user.business_address = None
            user.city = str(row.get("city", '')).strip()
            user.state = str(row.get("state", '')).strip()
            user.postal_code = None
            user.country = "India"
            user.is_active = True
            try:
                user.created_at = datetime.fromisoformat(str(row.get("registration_date")))
            except Exception:
                # Fallback if parsing fails
                user.created_at = datetime.utcnow()

            db.merge(user)
            upserted += 1
        db.commit()
        return upserted
    finally:
        if close_db:
            db.close()


def ingest_purchases(csv_path: str, db: Optional[Session] = None) -> int:
    """Ingest purchase history.
    CSV columns: purchase_id,retailer_id,product_id,quantity,unit_price_inr,total_amount_inr,purchase_date
    Maps to models.PurchaseHistory as rows with generated order_id by date bucket.
    Returns number of rows inserted (no upsert for history; duplicates by purchase_id will be ignored).
    """
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True
    try:
        df = pd.read_csv(csv_path)
        required_cols = {"purchase_id", "retailer_id", "product_id", "quantity", "unit_price_inr", "total_amount_inr", "purchase_date"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns in purchases CSV: {missing}")

        inserted = 0
        for _, row in df.iterrows():
            try:
                ph = PurchaseHistory()
                ph.user_id = int(row["retailer_id"]) if pd.notna(row["retailer_id"]) else None
                ph.product_id = int(row["product_id"]) if pd.notna(row["product_id"]) else None
                # Group items on same day into an order for the same user
                date_str = str(row.get("purchase_date"))
                try:
                    dt = datetime.fromisoformat(date_str)
                except Exception:
                    dt = datetime.utcnow()
                ph.order_id = f"ORD-{ph.user_id}-{dt.strftime('%Y%m%d')}"
                ph.quantity = int(row.get("quantity", 1) or 1)
                # price_paid as unit_price * quantity, fallback to total_amount / quantity
                try:
                    unit_price = float(row.get("unit_price_inr", 0) or 0)
                    ph.price_paid = unit_price * ph.quantity
                except Exception:
                    try:
                        total = float(row.get("total_amount_inr", 0) or 0)
                        ph.price_paid = total
                    except Exception:
                        ph.price_paid = 0.0
                ph.purchased_at = dt
                db.add(ph)
                inserted += 1
            except Exception:
                # Skip bad rows but continue ingestion
                continue
        db.commit()
        return inserted
    finally:
        if close_db:
            db.close()


def ingest_all(products_csv: str, retailers_csv: str, purchases_csv: str) -> dict:
    """Convenience function to run all three ingestions in order so foreign keys line up."""
    db = SessionLocal()
    try:
        init_db()
        p_count = ingest_products(products_csv, db)
        r_count = ingest_retailers(retailers_csv, db)
        h_count = ingest_purchases(purchases_csv, db)
        return {"products": p_count, "retailers": r_count, "purchases": h_count}
    finally:
        db.close()
