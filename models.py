from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(20))  # retailer, distributor
    business_name = Column(String(200))
    business_type = Column(String(100))  # kirana, restaurant, etc.
    contact_person = Column(String(100))
    email = Column(String(150), unique=True, index=True)
    phone = Column(String(20))
    business_address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))
    password_hash = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), index=True)
    category = Column(String(100), index=True)
    subcategory = Column(String(100))
    brand = Column(String(100))
    description = Column(Text)
    price = Column(Float)
    original_price = Column(Float)  # for showing discounts
    weight = Column(String(50))  # 50kg, 1L, etc.
    unit = Column(String(20))  # kg, L, packet, etc.
    stock_quantity = Column(Integer)
    min_order_quantity = Column(Integer, default=1)
    is_deal = Column(Boolean, default=False)
    discount_percent = Column(Float, default=0)
    cashback_offer = Column(Float, default=0)  # ₹1000 cashback
    is_combo = Column(Boolean, default=False)
    combo_products = Column(JSON)  # For combo packs
    image_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    supplier_id = Column(Integer, ForeignKey("users.id"))  # distributor
    created_at = Column(DateTime, default=datetime.utcnow)
    cost_price = Column(Float)  # Added for profit calculations

class DealPromotion(Base):
    __tablename__ = "deal_promotions"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200))
    description = Column(Text)
    banner_image = Column(String(500))
    discount_type = Column(String(50))  # percentage, fixed, cashback
    discount_value = Column(Float)
    min_order_amount = Column(Float)
    valid_from = Column(DateTime)
    valid_until = Column(DateTime)
    is_active = Column(Boolean, default=True)
    target_audience = Column(JSON)  # specific user types/cities
    product_id = Column(Integer, ForeignKey("products.id"))  # Added for linking
    created_at = Column(DateTime, default=datetime.utcnow)

class AIAssistantSession(Base):
    __tablename__ = "ai_assistant_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(100), unique=True)
    query = Column(Text)
    response = Column(Text)
    context = Column(JSON)  # user's business context
    created_at = Column(DateTime, default=datetime.utcnow)

class Wishlist(Base):
    __tablename__ = "wishlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    added_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    product = relationship("Product")

class PurchaseHistory(Base):
    __tablename__ = "purchase_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    order_id = Column(String(100))  # For grouping items in same order
    quantity = Column(Integer)
    price_paid = Column(Float)
    purchased_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(100), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_amount = Column(Float)
    tax_amount = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    shipping_cost = Column(Float, default=0)
    payment_method = Column(String(50))  # credit, net_terms, online, etc.
    payment_status = Column(String(50), default="pending")  # pending, paid, failed
    order_status = Column(String(50), default="placed")  # placed, confirmed, shipped, delivered, cancelled
    shipping_address = Column(Text)
    billing_address = Column(Text)
    notes = Column(Text)
    estimated_delivery = Column(DateTime)
    actual_delivery = Column(DateTime)
    invoice_number = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(100), ForeignKey("orders.order_id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_price = Column(Float)
    total_price = Column(Float)
    discount_applied = Column(Float, default=0)
    
    order = relationship("Order")
    product = relationship("Product")

class QuoteRequest(Base):
    __tablename__ = "quote_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(String(100), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    products_requested = Column(JSON)  # List of products with quantities
    message = Column(Text)
    status = Column(String(50), default="pending")  # pending, quoted, accepted, rejected
    quoted_amount = Column(Float)
    valid_until = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")

class UserAnalytics(Base):
    __tablename__ = "user_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0)
    avg_order_value = Column(Float, default=0)
    top_categories = Column(JSON)  # Most purchased categories
    top_products = Column(JSON)  # Most purchased products
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")

class ProductReview(Base):
    __tablename__ = "product_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    rating = Column(Integer)  # 1-5 stars
    review_text = Column(Text)
    is_verified_purchase = Column(Boolean, default=False)
    helpful_votes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    product = relationship("Product")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200))
    message = Column(Text)
    notification_type = Column(String(50))  # order_update, deal_alert, payment_reminder
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")

class BulkOrder(Base):
    __tablename__ = "bulk_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    upload_file_path = Column(String(500))
    processed_items = Column(JSON)
    failed_items = Column(JSON)
    status = Column(String(50), default="processing")  # processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")

# Pydantic models for API requests/responses
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class UserRegistration(BaseModel):
    user_type: str
    business_name: str
    business_type: str
    contact_person: str
    email: str
    phone: str
    business_address: str
    city: str
    state: str
    postal_code: str
    country: str
    password: str

class ProductResponse(BaseModel):
    id: int
    name: str
    category: str
    price: float
    original_price: Optional[float]
    discount_percent: float
    weight: str
    unit: str
    image_url: Optional[str]
    is_deal: bool
    cashback_offer: float
    is_combo: bool

class HomepageResponse(BaseModel):
    personalized_recommendations: List[ProductResponse]
    daily_deals: List[ProductResponse]
    trending_products: List[ProductResponse]
    low_stock_alerts: List[ProductResponse]
    seasonal_deals: List[Dict[str, Any]]

class AIAssistantRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class AIAssistantResponse(BaseModel):
    response: str
    session_id: str
    suggested_products: List[ProductResponse]
    follow_up_questions: List[str]

# New Pydantic models for B2B features
class OrderCreate(BaseModel):
    items: List[Dict[str, Any]]  # [{"product_id": 1, "quantity": 10}]
    shipping_address: str
    billing_address: Optional[str] = None
    payment_method: str
    notes: Optional[str] = None

class OrderResponse(BaseModel):
    order_id: str
    total_amount: float
    order_status: str
    payment_status: str
    estimated_delivery: Optional[str]
    created_at: str
    items: List[Dict[str, Any]]

class QuoteRequestCreate(BaseModel):
    products: List[Dict[str, Any]]  # [{"product_id": 1, "quantity": 100}]
    message: Optional[str] = None

class QuoteResponse(BaseModel):
    quote_id: str
    status: str
    quoted_amount: Optional[float]
    valid_until: Optional[str]
    message: Optional[str]

class AnalyticsResponse(BaseModel):
    total_orders: int
    total_spent: float
    avg_order_value: float
    top_categories: List[Dict[str, Any]]
    top_products: List[Dict[str, Any]]
    monthly_spending: List[Dict[str, Any]]

class BulkOrderCreate(BaseModel):
    csv_data: str  # Base64 encoded CSV or direct CSV content

class WishlistItem(BaseModel):
    product_id: int
    added_at: str

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: str
    action_url: Optional[str]

class ReviewCreate(BaseModel):
    product_id: int
    rating: int
    review_text: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    rating: int
    review_text: Optional[str]
    user_name: str
    is_verified_purchase: bool
    created_at: str
    helpful_votes: int
