from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
import logging

# Load .env file if present
load_dotenv()

# Setup logger
logger = logging.getLogger(__name__)

# Resolve and normalize database URL from environment
def _resolve_database_url() -> str:
    # Prefer DATABASE_URL, then DATABASE_URL_INTERNAL (Render Postgres internal URL)
    raw_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_INTERNAL")

    # Default to a file inside the container. On Render Docker, the writable path is
    # typically /opt/render/project/src
    render_sqlite_path = "/opt/render/project/src/qwipo.db"
    default_sqlite = (
        f"sqlite:////{render_sqlite_path.lstrip('/')}"
        if (os.getenv("RENDER") or os.path.exists("/opt/render/project/src"))
        else "sqlite:///./qwipo.db"
    )

    if not raw_url:
        logger.warning("DATABASE_URL not set; falling back to SQLite at %s", default_sqlite)
        return default_sqlite

    url = raw_url.strip().strip('"').strip("'")

    # Normalize legacy postgres scheme to SQLAlchemy's expected scheme
    if url.startswith("postgres://"):
        normalized = "postgresql://" + url[len("postgres://"):]
        logger.info("Normalized DATABASE_URL scheme from postgres:// to postgresql://")
        url = normalized

    logger.info("Using DATABASE_URL=%s", url)
    return url

DATABASE_URL = _resolve_database_url()

# Create engine with appropriate connect_args for SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    
    # Add sample data for testing
    add_sample_data()

def add_sample_data():
    """Add sample data for testing"""
    db = SessionLocal()
    try:
        from models import User, Product, DealPromotion, PurchaseHistory
        from passlib.context import CryptContext
        from datetime import datetime, timedelta
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Check if data already exists
        existing_user = db.query(User).first()
        if existing_user:
            return
        
        # Sample users
        users = [
            User(
                user_type="retailer",
                business_name="Sharma Kirana Store",
                business_type="kirana",
                contact_person="Raj Sharma",
                email="raj@sharma.com",
                phone="9876543210",
                business_address="123 Main Street",
                city="Mumbai",
                state="Maharashtra",
                postal_code="400001",
                country="India",
                password_hash=pwd_context.hash("password123")
            ),
            User(
                user_type="distributor",
                business_name="ABC Wholesale",
                business_type="wholesale",
                contact_person="Amit Kumar",
                email="amit@abc.com",
                phone="9876543211",
                business_address="456 Industrial Area",
                city="Delhi",
                state="Delhi",
                postal_code="110001",
                country="India",
                password_hash=pwd_context.hash("password123")
            )
        ]
        
        for user in users:
            db.add(user)
        db.commit()
        
        # Sample products
        products = [
            Product(
                name="Basmati Rice Premium",
                category="grains",
                subcategory="rice",
                brand="India Gate",
                description="Premium quality basmati rice",
                price=150.0,
                original_price=180.0,
                cost_price=120.0,
                weight="1kg",
                unit="kg",
                stock_quantity=100,
                is_deal=True,
                discount_percent=16.7,
                cashback_offer=10.0,
                image_url="/images/basmati-rice.jpg",
                supplier_id=2
            ),
            Product(
                name="Wheat Flour",
                category="grains",
                subcategory="flour",
                brand="Aashirvaad",
                description="Whole wheat flour",
                price=45.0,
                original_price=50.0,
                cost_price=35.0,
                weight="1kg",
                unit="kg",
                stock_quantity=200,
                is_deal=False,
                discount_percent=10.0,
                image_url="/images/wheat-flour.jpg",
                supplier_id=2
            ),
            Product(
                name="Toor Dal",
                category="pulses",
                subcategory="dal",
                brand="Organic India",
                description="Premium toor dal",
                price=120.0,
                original_price=130.0,
                cost_price=100.0,
                weight="1kg",
                unit="kg",
                stock_quantity=80,
                is_deal=True,
                discount_percent=7.7,
                cashback_offer=5.0,
                image_url="/images/toor-dal.jpg",
                supplier_id=2
            ),
            Product(
                name="Cooking Oil",
                category="oils",
                subcategory="cooking-oil",
                brand="Fortune",
                description="Refined sunflower oil",
                price=180.0,
                original_price=200.0,
                cost_price=150.0,
                weight="1L",
                unit="L",
                stock_quantity=60,
                is_deal=True,
                discount_percent=10.0,
                image_url="/images/cooking-oil.jpg",
                supplier_id=2
            ),
            Product(
                name="Sugar",
                category="sweeteners",
                subcategory="sugar",
                brand="Madhur",
                description="Pure white sugar",
                price=42.0,
                original_price=45.0,
                cost_price=38.0,
                weight="1kg",
                unit="kg",
                stock_quantity=150,
                is_deal=False,
                discount_percent=6.7,
                image_url="/images/sugar.jpg",
                supplier_id=2
            ),
            Product(
                name="Tea Leaves",
                category="beverages",
                subcategory="tea",
                brand="Tata Tea",
                description="Premium black tea",
                price=85.0,
                original_price=95.0,
                cost_price=70.0,
                weight="250g",
                unit="g",
                stock_quantity=90,
                is_deal=True,
                discount_percent=10.5,
                cashback_offer=3.0,
                image_url="/images/tea-leaves.jpg",
                supplier_id=2
            )
        ]
        
        for product in products:
            db.add(product)
        db.commit()
        
        # Sample deal promotions
        deals = [
            DealPromotion(
                title="Diwali Special - Rice & Dal Combo",
                description="Get 20% off on rice and dal combo",
                discount_type="percentage",
                discount_value=20.0,
                min_order_amount=500.0,
                valid_from=datetime.utcnow(),
                valid_until=datetime.utcnow() + timedelta(days=30),
                product_id=1
            ),
            DealPromotion(
                title="Bulk Purchase Discount",
                description="₹100 cashback on orders above ₹2000",
                discount_type="cashback",
                discount_value=100.0,
                min_order_amount=2000.0,
                valid_from=datetime.utcnow(),
                valid_until=datetime.utcnow() + timedelta(days=15),
                product_id=2
            )
        ]
        
        for deal in deals:
            db.add(deal)
        db.commit()
        
        # Sample purchase history
        purchase_history = [
            PurchaseHistory(
                user_id=1,
                product_id=1,
                order_id="ORD001",
                quantity=2,
                price_paid=300.0,
                purchased_at=datetime.utcnow() - timedelta(days=5)
            ),
            PurchaseHistory(
                user_id=1,
                product_id=3,
                order_id="ORD001",
                quantity=1,
                price_paid=120.0,
                purchased_at=datetime.utcnow() - timedelta(days=5)
            ),
            PurchaseHistory(
                user_id=1,
                product_id=2,
                order_id="ORD002",
                quantity=3,
                price_paid=135.0,
                purchased_at=datetime.utcnow() - timedelta(days=10)
            )
        ]
        
        for purchase in purchase_history:
            db.add(purchase)
        db.commit()
        
        print("Sample data added successfully!")
        
    except Exception as e:
        print(f"Error adding sample data: {e}")
        db.rollback()
    finally:
        db.close()
