from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import csv
import io

from database import get_db
from models import (
    Order, OrderItem, QuoteRequest, UserAnalytics, ProductReview,
    Notification, BulkOrder, Wishlist, DealPromotion,
    OrderCreate, OrderResponse, QuoteRequestCreate, QuoteResponse,
    AnalyticsResponse, BulkOrderCreate, ReviewCreate, ReviewResponse
)

router = APIRouter()

# Utility helpers

def _generate_order_id() -> str:
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"


def _generate_quote_id() -> str:
    return f"QTE-{uuid.uuid4().hex[:8].upper()}"


def _create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    action_url: str | None = None,
) -> None:
    n = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False,
        action_url=action_url,
        created_at=datetime.utcnow(),
    )
    db.add(n)
    # caller is responsible to commit


# Orders ----------------------------------------------------------------------

@router.post("/api/orders", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    user_id: int = Query(..., description="User placing the order"),
    db: Session = Depends(get_db),
):
    try:
        # Fetch product prices and compute totals
        items_out: List[Dict[str, Any]] = []
        subtotal = 0.0
        for it in order.items:
            pid = int(it.get("product_id"))
            qty = int(it.get("quantity", 1))
            if qty <= 0:
                raise HTTPException(status_code=400, detail="Quantity must be positive")
            p = db.execute(text("SELECT id, name, price, stock_quantity FROM products WHERE id=:pid AND is_active=1"), {"pid": pid}).fetchone()
            if not p:
                raise HTTPException(status_code=404, detail=f"Product {pid} not found")
            if p.stock_quantity is not None and p.stock_quantity < qty:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for product {p.name}")
            line_total = float(p.price) * qty
            subtotal += line_total
            items_out.append({
                "product_id": p.id,
                "name": p.name,
                "quantity": qty,
                "unit_price": float(p.price),
                "total_price": line_total,
            })
        tax = round(subtotal * 0.05, 2)  # simple 5% tax
        shipping = 0.0 if subtotal >= 2000 else 49.0
        total = round(subtotal + tax + shipping, 2)

        oid = _generate_order_id()
        now = datetime.utcnow()
        est = now + timedelta(days=3)

        new_order = Order(
            order_id=oid,
            user_id=user_id,
            total_amount=total,
            tax_amount=tax,
            discount_amount=0.0,
            shipping_cost=shipping,
            payment_method=order.payment_method,
            payment_status="pending",
            order_status="placed",
            shipping_address=order.shipping_address,
            billing_address=order.billing_address or order.shipping_address,
            notes=order.notes,
            estimated_delivery=est,
            created_at=now,
            updated_at=now,
        )
        db.add(new_order)
        db.flush()

        # Insert items and reduce stock
        for it in items_out:
            db.add(OrderItem(
                order_id=oid,
                product_id=it["product_id"],
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                total_price=it["total_price"],
            ))
            db.execute(
                text("UPDATE products SET stock_quantity = stock_quantity - :q WHERE id = :pid AND stock_quantity >= :q"),
                {"q": it["quantity"], "pid": it["product_id"]}
            )

        # Create notification
        _create_notification(
            db,
            user_id,
            title="Order Placed",
            message=f"Your order {oid} has been placed successfully.",
            notification_type="order_placed",
        )

        db.commit()

        return OrderResponse(
            order_id=oid,
            total_amount=total,
            order_status=new_order.order_status,
            payment_status=new_order.payment_status,
            estimated_delivery=new_order.estimated_delivery.isoformat() if new_order.estimated_delivery else None,
            created_at=new_order.created_at.isoformat(),
            items=items_out,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating order: {e}")


@router.get("/api/orders/history")
async def order_history(
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    orders = db.execute(text("SELECT * FROM orders WHERE user_id=:uid ORDER BY created_at DESC"), {"uid": user_id}).fetchall()
    resp = []
    for o in orders:
        items = db.execute(text("""
            SELECT oi.product_id, p.name, oi.quantity, oi.unit_price, oi.total_price
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id = :oid
        """), {"oid": o.order_id}).fetchall()
        resp.append({
            "order_id": o.order_id,
            "total_amount": float(o.total_amount or 0),
            "order_status": o.order_status,
            "payment_status": o.payment_status,
            "estimated_delivery": o.estimated_delivery.isoformat() if o.estimated_delivery else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items": [dict(row._mapping) for row in items],
        })
    return {"orders": resp, "total": len(resp)}


@router.get("/api/orders/{order_id}/track")
async def track_order(order_id: str, db: Session = Depends(get_db)):
    o = db.execute(text("SELECT * FROM orders WHERE order_id=:oid"), {"oid": order_id}).fetchone()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    timeline = [
        {"status": "placed", "time": (o.created_at or datetime.utcnow()).isoformat()},
    ]
    if o.order_status in ("confirmed", "shipped", "delivered"):
        timeline.append({"status": "confirmed", "time": (o.created_at or datetime.utcnow()).isoformat()})
    if o.order_status in ("shipped", "delivered"):
        timeline.append({"status": "shipped", "time": (o.updated_at or datetime.utcnow()).isoformat()})
    if o.order_status == "delivered":
        timeline.append({"status": "delivered", "time": (o.actual_delivery or o.updated_at or datetime.utcnow()).isoformat()})
    return {
        "order_id": o.order_id,
        "order_status": o.order_status,
        "estimated_delivery": o.estimated_delivery.isoformat() if o.estimated_delivery else None,
        "timeline": timeline,
    }


@router.post("/api/orders/repeat-last", response_model=OrderResponse)
async def repeat_last_order(user_id: int = Query(...), db: Session = Depends(get_db)):
    last = db.execute(text("SELECT * FROM orders WHERE user_id=:uid ORDER BY created_at DESC LIMIT 1"), {"uid": user_id}).fetchone()
    if not last:
        raise HTTPException(status_code=404, detail="No previous orders to repeat")
    items = db.execute(text("SELECT product_id, quantity FROM order_items WHERE order_id=:oid"), {"oid": last.order_id}).fetchall()
    req = OrderCreate(
        items=[{"product_id": r.product_id, "quantity": r.quantity} for r in items],
        shipping_address=last.shipping_address,
        billing_address=last.billing_address,
        payment_method=last.payment_method or "online",
        notes=f"Repeat of {last.order_id}",
    )
    return await create_order(req, user_id, db)


# Bulk Orders -----------------------------------------------------------------

@router.post("/api/bulk-orders")
async def bulk_order_upload(payload: BulkOrderCreate, user_id: int = Query(...), db: Session = Depends(get_db)):
    try:
        # Parse CSV from string
        csv_text = payload.csv_data
        if not csv_text:
            raise HTTPException(status_code=400, detail="csv_data is required")
        reader = csv.DictReader(io.StringIO(csv_text))
        items = []
        for row in reader:
            try:
                items.append({"product_id": int(row.get("product_id")), "quantity": int(row.get("quantity"))})
            except Exception:
                continue
        if not items:
            raise HTTPException(status_code=400, detail="No valid items in CSV")
        # Create order using items
        req = OrderCreate(
            items=items,
            shipping_address="Same as default",
            billing_address=None,
            payment_method="online",
            notes="Bulk CSV order",
        )
        order_resp = await create_order(req, user_id, db)
        return {"status": "processed", "order": order_resp}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing bulk order: {e}")


# Analytics -------------------------------------------------------------------

@router.get("/api/analytics", response_model=AnalyticsResponse)
async def purchase_analytics(user_id: int = Query(...), db: Session = Depends(get_db)):
    # Totals
    tot = db.execute(text("SELECT COUNT(*) c, COALESCE(SUM(total_amount),0) s FROM orders WHERE user_id=:uid"), {"uid": user_id}).fetchone()
    avg = 0.0
    if tot.c and tot.c > 0:
        avg = float(tot.s) / float(tot.c)

    # Top categories/products via purchase_history
    top_cat = db.execute(text("""
        SELECT p.category, COUNT(*) cnt
        FROM purchase_history ph
        JOIN products p ON p.id = ph.product_id
        WHERE ph.user_id = :uid
        GROUP BY p.category
        ORDER BY cnt DESC
        LIMIT 5
    """), {"uid": user_id}).fetchall()

    top_prod = db.execute(text("""
        SELECT p.id, p.name, COUNT(*) cnt
        FROM purchase_history ph
        JOIN products p ON p.id = ph.product_id
        WHERE ph.user_id = :uid
        GROUP BY p.id, p.name
        ORDER BY cnt DESC
        LIMIT 5
    """), {"uid": user_id}).fetchall()

    # Monthly spending last 6 months
    monthly = db.execute(text("""
        SELECT strftime('%Y-%m', created_at) ym, COALESCE(SUM(total_amount),0) amt
        FROM orders
        WHERE user_id = :uid
        GROUP BY ym
        ORDER BY ym DESC
        LIMIT 6
    """), {"uid": user_id}).fetchall()

    return AnalyticsResponse(
        total_orders=int(tot.c or 0),
        total_spent=float(tot.s or 0.0),
        avg_order_value=round(avg, 2),
        top_categories=[{"category": r.category, "count": r.cnt} for r in top_cat],
        top_products=[{"product_id": r.id, "name": r.name, "count": r.cnt} for r in top_prod],
        monthly_spending=[{"month": r.ym, "amount": float(r.amt)} for r in monthly][::-1],
    )


# Quotes ----------------------------------------------------------------------

@router.post("/api/quotes", response_model=QuoteResponse)
async def create_quote(req: QuoteRequestCreate, user_id: int = Query(...), db: Session = Depends(get_db)):
    qid = _generate_quote_id()
    qr = QuoteRequest(
        quote_id=qid,
        user_id=user_id,
        products_requested=req.products,
        message=req.message,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(qr)
    db.commit()
    return QuoteResponse(quote_id=qid, status="pending", quoted_amount=None, valid_until=None, message=req.message)


@router.get("/api/quotes")
async def list_quotes(user_id: int = Query(...), db: Session = Depends(get_db)):
    q = db.execute(text("SELECT quote_id, status, quoted_amount, valid_until, created_at FROM quote_requests WHERE user_id=:uid ORDER BY created_at DESC"), {"uid": user_id}).fetchall()
    return {"quotes": [dict(row._mapping) for row in q]}


# Wishlist --------------------------------------------------------------------

@router.post("/api/wishlist")
async def add_wishlist(product_id: int = Query(...), user_id: int = Query(...), db: Session = Depends(get_db)):
    exists = db.execute(text("SELECT id FROM wishlists WHERE user_id=:u AND product_id=:p"), {"u": user_id, "p": product_id}).fetchone()
    if exists:
        return {"status": "exists"}
    w = Wishlist(user_id=user_id, product_id=product_id)
    db.add(w)
    db.commit()
    return {"status": "added"}


@router.get("/api/wishlist")
async def list_wishlist(user_id: int = Query(...), db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT w.product_id, p.name, p.price, p.image_url, w.added_at
        FROM wishlists w JOIN products p ON p.id = w.product_id
        WHERE w.user_id = :uid
        ORDER BY w.added_at DESC
    """), {"uid": user_id}).fetchall()
    return {"items": [dict(r._mapping) for r in rows]}


@router.delete("/api/wishlist/{product_id}")
async def remove_wishlist(product_id: int, user_id: int = Query(...), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM wishlists WHERE user_id=:u AND product_id=:p"), {"u": user_id, "p": product_id})
    db.commit()
    return {"status": "removed"}


# Reviews ---------------------------------------------------------------------

@router.post("/api/reviews", response_model=ReviewResponse)
async def add_review(payload: ReviewCreate, user_id: int = Query(...), db: Session = Depends(get_db)):
    # verify purchase
    purchased = db.execute(text("SELECT 1 FROM purchase_history WHERE user_id=:u AND product_id=:p LIMIT 1"), {"u": user_id, "p": payload.product_id}).fetchone()
    r = ProductReview(
        user_id=user_id,
        product_id=payload.product_id,
        rating=payload.rating,
        review_text=payload.review_text,
        is_verified_purchase=bool(purchased),
        created_at=datetime.utcnow(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    uname = db.execute(text("SELECT business_name FROM users WHERE id=:u"), {"u": user_id}).fetchone()
    return ReviewResponse(
        id=r.id,
        rating=r.rating,
        review_text=r.review_text,
        user_name=(uname.business_name if uname else "User"),
        is_verified_purchase=r.is_verified_purchase,
        created_at=r.created_at.isoformat(),
        helpful_votes=r.helpful_votes or 0,
    )


@router.get("/api/reviews/{product_id}")
async def list_reviews(product_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT r.id, r.rating, r.review_text, r.is_verified_purchase, r.helpful_votes, r.created_at, u.business_name as user_name
        FROM product_reviews r JOIN users u ON u.id = r.user_id
        WHERE r.product_id = :p
        ORDER BY r.created_at DESC
    """), {"p": product_id}).fetchall()
    return {"reviews": [dict(r._mapping) for r in rows]}


# Notifications ---------------------------------------------------------------

@router.get("/api/notifications")
async def list_notifications(user_id: int = Query(...), db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT id, title, message, notification_type, is_read, action_url, created_at FROM notifications WHERE user_id=:u ORDER BY created_at DESC"), {"u": user_id}).fetchall()
    unread = db.execute(text("SELECT COUNT(*) FROM notifications WHERE user_id=:u AND is_read=0"), {"u": user_id}).scalar() or 0
    return {"notifications": [dict(r._mapping) for r in rows], "unread_count": int(unread)}


@router.post("/api/notifications/mark-read")
async def mark_notification_read(id: int = Query(...), user_id: int = Query(...), db: Session = Depends(get_db)):
    res = db.execute(text("UPDATE notifications SET is_read=1 WHERE id=:id AND user_id=:u"), {"id": id, "u": user_id})
    db.commit()
    return {"status": "ok", "updated": res.rowcount}


@router.post("/api/notifications/mark-all-read")
async def mark_all_notifications_read(user_id: int = Query(...), db: Session = Depends(get_db)):
    res = db.execute(text("UPDATE notifications SET is_read=1 WHERE user_id=:u AND is_read=0"), {"u": user_id})
    db.commit()
    return {"status": "ok", "updated": res.rowcount}


@router.post("/api/notifications/payment-reminders")
async def generate_payment_reminders(user_id: int = Query(...), db: Session = Depends(get_db)):
    # Find pending/unpaid orders and generate reminders
    orders = db.execute(text("""
        SELECT order_id, total_amount, created_at
        FROM orders
        WHERE user_id = :u AND payment_status != 'paid'
        ORDER BY created_at DESC
        LIMIT 5
    """), {"u": user_id}).fetchall()
    count = 0
    for o in orders:
        _create_notification(
            db,
            user_id,
            title="Payment Reminder",
            message=f"Payment pending for order {o.order_id}. Amount: ₹{float(o.total_amount or 0):.2f}.",
            notification_type="payment_reminder",
            action_url=f"/orders/{o.order_id}"
        )
        count += 1
    db.commit()
    return {"status": "created", "reminders": count}


@router.post("/api/notifications/deal-alerts")
async def generate_deal_alerts(user_id: int = Query(...), db: Session = Depends(get_db)):
    # Pick top active deals and notify
    deals = db.execute(text("""
        SELECT id, title, description, valid_until,
               CASE WHEN valid_until IS NULL THEN 1 ELSE 0 END AS is_null
        FROM deal_promotions
        WHERE is_active = 1 AND (valid_until IS NULL OR valid_until > CURRENT_TIMESTAMP)
        ORDER BY is_null ASC, valid_until DESC, id DESC
        LIMIT 3
    """))
    count = 0
    for d in deals:
        _create_notification(
            db,
            user_id,
            title="Deal Alert",
            message=f"{d.title}: {d.description}",
            notification_type="deal_alert",
            action_url=f"/deals/{d.id}"
        )
        count += 1
    db.commit()
    return {"status": "created", "alerts": count}
