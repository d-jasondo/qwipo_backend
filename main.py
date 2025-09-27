from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import uvicorn
import logging
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

from models import (
    UserRegistration, HomepageResponse, ProductResponse, 
    AIAssistantRequest, AIAssistantResponse
)
from database import get_db, init_db
from recommendation_engine import EnhancedRecommendationEngine
from ai_assistant import AIRetailAssistant
from cache import cache
from b2b_features import router as b2b_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Qwipo B2B Marketplace API",
    description="AI-powered backend for Qwipo's B2B marketplace with intelligent recommendations",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount B2B feature routes
app.include_router(b2b_router)

# CORS configuration to allow frontend (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    try:
        init_db()
        logger.info("Qwipo Backend Started Successfully")
        logger.info("Database initialized with sample data")
        logger.info("API Documentation available at: http://localhost:8000/docs")
    except Exception as e:
        logger.error(f"Startup error: {e}")

# Homepage endpoint matching your design
@app.get("/api/homepage", response_model=HomepageResponse)
async def get_homepage(
    user_id: int = Query(..., description="User ID for personalized recommendations"),
    db: Session = Depends(get_db)
):
    """
    Get homepage data with personalized recommendations
    
    Returns:
    - Personalized recommendations based on user's business and location
    - Daily deals and promotions
    - Trending products in user's area
    - Low stock alerts for frequently purchased items
    - Seasonal deals and offers
    """
    try:
        logger.info(f"Getting homepage recommendations for user {user_id}")
        engine = EnhancedRecommendationEngine(db)
        recommendations = engine.get_homepage_recommendations(user_id)
        
        logger.info(f"Successfully generated homepage recommendations for user {user_id}")
        return recommendations
        
    except Exception as e:
        logger.error(f"Homepage error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error loading homepage recommendations")

# Product detail page with AI suggestions
@app.get("/api/products/{product_id}")
async def get_product_detail(
    product_id: int,
    user_id: int = Query(..., description="User ID for personalized suggestions"),
    db: Session = Depends(get_db)
):
    """
    Get product details with AI-powered suggestions
    
    Returns:
    - Complete product information
    - Similar products
    - Frequently bought together items
    - New products in same category
    """
    try:
        logger.info(f"Getting product details for product {product_id}, user {user_id}")
        engine = EnhancedRecommendationEngine(db)
        
        # Get product basic info
        product_query = text("SELECT * FROM products WHERE id = :product_id AND is_active = 1")
        product_result = db.execute(product_query, {'product_id': product_id})
        product_data = product_result.fetchone()
        
        if not product_data:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get recommendations
        recommendations = engine.get_product_page_recommendations(product_id, user_id)
        
        # Format product data
        product_info = {
            "id": product_data[0],
            "name": product_data[1],
            "category": product_data[2],
            "subcategory": product_data[3],
            "brand": product_data[4],
            "description": product_data[5],
            "price": float(product_data[6]) if product_data[6] else 0.0,
            "original_price": float(product_data[7]) if product_data[7] else None,
            "weight": product_data[8],
            "unit": product_data[9],
            "stock_quantity": product_data[10],
            "min_order_quantity": product_data[11],
            "is_deal": bool(product_data[12]),
            "discount_percent": product_data[13] or 0,
            "cashback_offer": product_data[14] or 0,
            "image_url": product_data[17],
            "specifications": {
                "weight": product_data[8],
                "unit": product_data[9],
                "brand": product_data[4],
                "category": product_data[2]
            }
        }
        
        # Calculate discount if not provided
        if product_info['original_price'] and product_info['original_price'] > product_info['price']:
            product_info['discount_percent'] = round(
                (product_info['original_price'] - product_info['price']) / product_info['original_price'] * 100, 1
            )
        
        response = {
            "product": product_info,
            "recommendations": recommendations
        }
        
        logger.info(f"Successfully retrieved product details for product {product_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product detail error for product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Error loading product details")

# AI Retail Assistant endpoint
@app.post("/api/ai-assistant", response_model=AIAssistantResponse)
async def ai_assistant_query(
    request: AIAssistantRequest,
    user_id: int = Query(..., description="User ID for personalized AI responses"),
    db: Session = Depends(get_db)
):
    """
    AI Retail Assistant for business queries
    
    Examples:
    - "What should I stock for Diwali?"
    - "Which products have the best profit margins?"
    - "Generate a shopping list for my kirana store"
    - "What are the trending products in Mumbai?"
    """
    try:
        logger.info(f"Processing AI query for user {user_id}: {request.query}")
        assistant = AIRetailAssistant(db)
        response = assistant.process_query(user_id, request.query, request.session_id)
        
        # Generate session ID if not provided
        session_id = request.session_id or f"session_{user_id}_{hash(request.query)}"
        
        ai_response = AIAssistantResponse(
            response=response["response"],
            session_id=session_id,
            suggested_products=response["suggested_products"],
            follow_up_questions=response["follow_up_questions"]
        )
        
        logger.info(f"Successfully processed AI query for user {user_id}")
        return ai_response
        
    except Exception as e:
        logger.error(f"AI Assistant error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error processing AI query")

# Deals and promotions endpoint
@app.get("/api/deals")
async def get_deals_promotions(
    user_id: int = Query(..., description="User ID for personalized deals"),
    deal_type: str = Query("daily", description="Type of deals: daily, seasonal, clearance"),
    db: Session = Depends(get_db)
):
    """
    Get deals and promotions
    
    Deal Types:
    - daily: Daily deals and flash sales
    - seasonal: Seasonal promotions (Diwali, Winter, etc.)
    - clearance: Clearance and bulk deals
    """
    try:
        logger.info(f"Getting {deal_type} deals for user {user_id}")
        engine = EnhancedRecommendationEngine(db)
        
        if deal_type == "daily":
            deals = engine.get_daily_deals(user_id, limit=20)
            title = "Daily Deals & Flash Sales"
        elif deal_type == "seasonal":
            deals = engine.get_popular_products(20)  # In production, implement seasonal logic
            title = "Seasonal Promotions"
        elif deal_type == "clearance":
            # Get products with high discounts
            query = text("""
                SELECT p.*
                FROM products p
                WHERE p.is_active = 1
                AND p.discount_percent >= 15
                ORDER BY p.discount_percent DESC
                LIMIT 20
            """)
            result = db.execute(query)
            deals = engine._format_products(result)
            title = "Clearance & Bulk Deals"
        else:
            deals = engine.get_popular_products(20)
            title = "Popular Deals"
        
        response = {
            "deal_type": deal_type,
            "deals": deals,
            "title": title,
            "total_deals": len(deals)
        }
        
        logger.info(f"Successfully retrieved {len(deals)} {deal_type} deals for user {user_id}")
        return response
        
    except Exception as e:
        logger.error(f"Deals error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error loading deals")

# Search products endpoint
@app.get("/api/search")
async def search_products(
    query: str = Query(..., description="Search query"),
    user_id: int = Query(..., description="User ID for personalized results"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    limit: int = Query(20, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Search products with filters
    """
    try:
        logger.info(f"Searching products for query: {query}, user: {user_id}")
        
        # Build search query
        conditions = ["p.is_active = 1"]
        params = {'limit': limit}
        
        # Text search
        if query:
            conditions.append("(p.name LIKE :query OR p.description LIKE :query OR p.category LIKE :query)")
            params['query'] = f"%{query}%"
        
        # Category filter
        if category:
            conditions.append("p.category = :category")
            params['category'] = category
        
        # Price filters
        if min_price is not None:
            conditions.append("p.price >= :min_price")
            params['min_price'] = min_price
            
        if max_price is not None:
            conditions.append("p.price <= :max_price")
            params['max_price'] = max_price
        
        where_clause = " AND ".join(conditions)
        
        search_query = text(f"""
            SELECT p.*, COUNT(ph.id) as popularity
            FROM products p
            LEFT JOIN purchase_history ph ON p.id = ph.product_id
            WHERE {where_clause}
            GROUP BY p.id
            ORDER BY popularity DESC, p.created_at DESC
            LIMIT :limit
        """)
        
        result = db.execute(search_query, params)
        engine = EnhancedRecommendationEngine(db)
        products = engine._format_products(result)
        
        response = {
            "query": query,
            "results": products,
            "total_results": len(products),
            "filters_applied": {
                "category": category,
                "min_price": min_price,
                "max_price": max_price
            }
        }
        
        logger.info(f"Search returned {len(products)} results for query: {query}")
        return response
        
    except Exception as e:
        logger.error(f"Search error for query '{query}': {e}")
        raise HTTPException(status_code=500, detail="Error performing search")

# User registration endpoint
@app.post("/api/register")
async def register_user(
    registration: UserRegistration,
    db: Session = Depends(get_db)
):
    """
    Register a new user (retailer or distributor)
    """
    try:
        logger.info(f"Registering new user: {registration.email}")
        from models import User
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Check if user already exists
        existing_user_query = text("SELECT id FROM users WHERE email = :email")
        existing_user = db.execute(existing_user_query, {'email': registration.email}).fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        new_user = User(
            user_type=registration.user_type,
            business_name=registration.business_name,
            business_type=registration.business_type,
            contact_person=registration.contact_person,
            email=registration.email,
            phone=registration.phone,
            business_address=registration.business_address,
            city=registration.city,
            state=registration.state,
            postal_code=registration.postal_code,
            country=registration.country,
            password_hash=pwd_context.hash(registration.password),
            created_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"Successfully registered user: {registration.email} with ID: {new_user.id}")
        
        return {
            "status": "success",
            "message": "User registered successfully",
            "user_id": new_user.id,
            "business_name": new_user.business_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error for {registration.email}: {e}")
        raise HTTPException(status_code=500, detail="Error during registration")

# Get user profile
@app.get("/api/users/{user_id}")
async def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user profile information"""
    try:
        query = text("""
            SELECT u.*, COUNT(DISTINCT ph.product_id) as products_ordered,
                   COUNT(ph.id) as total_orders
            FROM users u
            LEFT JOIN purchase_history ph ON u.id = ph.user_id
            WHERE u.id = :user_id
            GROUP BY u.id
        """)
        
        result = db.execute(query, {'user_id': user_id})
        user_data = result.fetchone()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user_data[0],
            "user_type": user_data[1],
            "business_name": user_data[2],
            "business_type": user_data[3],
            "contact_person": user_data[4],
            "email": user_data[5],
            "phone": user_data[6],
            "city": user_data[8],
            "state": user_data[9],
            "country": user_data[11],
            "is_active": user_data[12],
            "created_at": user_data[13],
            "stats": {
                "products_ordered": user_data[15] or 0,
                "total_orders": user_data[16] or 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error loading user profile")

# Get categories
@app.get("/api/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Get all product categories"""
    try:
        query = text("""
            SELECT category, COUNT(*) as product_count
            FROM products
            WHERE is_active = 1
            GROUP BY category
            ORDER BY product_count DESC
        """)
        
        result = db.execute(query)
        categories = [{"name": row[0], "product_count": row[1]} for row in result.fetchall()]
        
        return {
            "categories": categories,
            "total_categories": len(categories)
        }
        
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail="Error loading categories")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Qwipo Backend API",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "features": [
            "AI-powered recommendations",
            "Personalized homepage",
            "Smart product suggestions",
            "Retail assistant chatbot",
            "Advanced search & filtering"
        ]
    }

# Mirror health under /api for frontend proxy convenience
@app.get("/api/health")
async def api_health_check():
    return await health_check()

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to Qwipo B2B Marketplace API",
        "version": "2.0.0",
        "documentation": "/docs",
        "health_check": "/health",
        "features": {
            "homepage": "/api/homepage?user_id=1",
            "ai_assistant": "/api/ai-assistant",
            "product_details": "/api/products/{product_id}?user_id=1",
            "deals": "/api/deals?user_id=1",
            "search": "/api/search?query=rice&user_id=1"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1,  # Use 1 worker for development
        log_level="info"
    )
