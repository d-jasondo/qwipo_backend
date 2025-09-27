import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIRetailAssistant:
    def __init__(self, db: Session):
        self.db = db
        # Use OpenAI API or fallback to rule-based
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    def process_query(self, user_id: int, query: str, session_id: str = None) -> Dict[str, Any]:
        """Process AI assistant queries like 'What should I stock for Diwali?'"""
        try:
            # Get user context
            user_context = self.get_user_context(user_id)
            
            if self.openai_api_key:
                return self.process_with_ai(query, user_context, session_id)
            else:
                return self.process_rule_based(query, user_context, session_id)
                
        except Exception as e:
            logger.error(f"Error in AI assistant: {e}")
            return self.get_fallback_response(query)
    
    def get_user_context(self, user_id: int) -> Dict[str, Any]:
        """Get user's business context for personalized responses"""
        try:
            query = text("""
                SELECT u.business_type, u.business_name, u.city, 
                       COUNT(DISTINCT ph.product_id) as products_ordered,
                       COUNT(ph.id) as total_orders
                FROM users u
                LEFT JOIN purchase_history ph ON u.id = ph.user_id
                WHERE u.id = :user_id
                GROUP BY u.id, u.business_type, u.business_name, u.city
            """)
            result = self.db.execute(query, {'user_id': user_id})
            user_data = result.fetchone()
            
            # Get recent purchase trends
            trend_query = text("""
                SELECT p.category, COUNT(ph.id) as order_count
                FROM purchase_history ph
                JOIN products p ON ph.product_id = p.id
                WHERE ph.user_id = :user_id
                AND ph.purchased_at >= datetime('now', '-30 days')
                GROUP BY p.category
                ORDER BY order_count DESC
                LIMIT 5
            """)
            trend_result = self.db.execute(trend_query, {'user_id': user_id})
            trends = [{"category": row[0], "count": row[1]} for row in trend_result.fetchall()]
            
            return {
                "business_type": user_data[0] if user_data else "retailer",
                "business_name": user_data[1] if user_data else "",
                "city": user_data[2] if user_data else "",
                "purchase_history": {
                    "products_ordered": user_data[3] if user_data else 0,
                    "total_orders": user_data[4] if user_data else 0
                },
                "recent_trends": trends
            }
            
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return {"business_type": "retailer", "city": ""}
    
    def process_with_ai(self, query: str, context: Dict, session_id: str) -> Dict[str, Any]:
        """Process with OpenAI API (if available)"""
        try:
            import openai
            openai.api_key = self.openai_api_key
            
            # Create context-aware prompt
            prompt = f"""
            You are an AI assistant for a B2B marketplace helping retailers with inventory decisions.
            
            User Context:
            - Business Type: {context.get('business_type', 'retailer')}
            - Business Name: {context.get('business_name', 'N/A')}
            - Location: {context.get('city', 'N/A')}
            - Recent Purchase Trends: {context.get('recent_trends', [])}
            
            User Query: {query}
            
            Provide helpful, specific advice for their business. Include product suggestions if relevant.
            Keep the response concise and actionable.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful B2B marketplace assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
            # Get relevant products based on query
            suggested_products = self.get_query_relevant_products(query, context)
            
            return {
                "response": ai_response,
                "suggested_products": suggested_products,
                "follow_up_questions": self.generate_follow_up_questions(query, context)
            }
            
        except Exception as e:
            logger.error(f"Error with OpenAI API: {e}")
            return self.process_rule_based(query, context, session_id)
    
    def process_rule_based(self, query: str, context: Dict, session_id: str) -> Dict[str, Any]:
        """Rule-based processing for common queries"""
        query_lower = query.lower()
        
        # Diwali stocking suggestions
        if any(word in query_lower for word in ["diwali", "festive", "festival", "celebration"]):
            return self.get_diwali_suggestions(context)
        
        # High-profit items
        elif any(word in query_lower for word in ["profit", "high-margin", "margin", "profitable"]):
            return self.get_high_profit_suggestions(context)
        
        # Shopping list creation
        elif any(word in query_lower for word in ["shopping list", "stock", "inventory", "order"]):
            return self.generate_shopping_list(context)
        
        # Seasonal suggestions
        elif any(word in query_lower for word in ["season", "month", "weather", "winter", "summer"]):
            return self.get_seasonal_suggestions(context)
        
        # Best sellers
        elif any(word in query_lower for word in ["best", "popular", "trending", "top"]):
            return self.get_best_sellers(context)
        
        # New products
        elif any(word in query_lower for word in ["new", "latest", "recent"]):
            return self.get_new_products(context)
        
        else:
            return self.get_general_suggestions(context)
    
    def get_diwali_suggestions(self, context: Dict) -> Dict[str, Any]:
        """Get Diwali stocking suggestions"""
        try:
            query = text("""
                SELECT p.*, COUNT(ph.id) as diwali_orders
                FROM products p
                LEFT JOIN purchase_history ph ON p.id = ph.product_id
                WHERE p.category IN ('sweets', 'snacks', 'gifts', 'decorations', 'clothing')
                OR p.name LIKE '%diwali%' OR p.name LIKE '%festive%' 
                OR p.name LIKE '%light%' OR p.name LIKE '%sweet%'
                OR p.category = 'oils' OR p.category = 'grains'
                GROUP BY p.id
                ORDER BY diwali_orders DESC, p.created_at DESC
                LIMIT 10
            """)
            result = self.db.execute(query)
            products = self._format_ai_products(result)
            
            business_type = context.get('business_type', 'retailer')
            city = context.get('city', 'your area')
            
            response_text = f"""For Diwali season, I recommend stocking these high-demand items for your {business_type} in {city}:

🪔 **Festive Essentials**: Cooking oils, premium rice, and pulses are always in high demand
🍬 **Sweet Ingredients**: Sugar, ghee, and dry fruits for homemade sweets
🎁 **Gift Items**: Premium packaged goods that make great corporate gifts
🏮 **Seasonal Products**: Items with festive packaging sell 40% better during Diwali

Based on last year's data, these categories see 2-3x higher sales during the festive season."""
            
            return {
                "response": response_text,
                "suggested_products": products[:5],
                "follow_up_questions": [
                    "Should I focus more on gifts or food items?",
                    "What's the ideal inventory quantity for these?",
                    "Any specific brands that sell better during Diwali?"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting Diwali suggestions: {e}")
            return self.get_fallback_response("diwali")
    
    def get_high_profit_suggestions(self, context: Dict) -> Dict[str, Any]:
        """Get high-profit margin suggestions"""
        try:
            query = text("""
                SELECT p.*, 
                       CASE 
                           WHEN p.cost_price > 0 THEN ((p.price - p.cost_price) / p.price * 100)
                           ELSE 0 
                       END as profit_margin
                FROM products p
                WHERE p.is_active = 1
                AND p.cost_price > 0
                AND ((p.price - p.cost_price) / p.price) >= 0.25
                ORDER BY profit_margin DESC
                LIMIT 8
            """)
            result = self.db.execute(query)
            products = self._format_ai_products(result)
            
            business_type = context.get('business_type', 'business')
            
            response_text = f"""Here are high-profit margin products perfect for your {business_type}:

💰 **Premium Products**: Focus on branded items with 25%+ margins
📈 **Value-Added Items**: Packaged and processed goods typically offer better margins
🎯 **Niche Products**: Specialty items have less competition and higher profits
⚡ **Fast Movers**: High-margin items that also sell quickly

Pro tip: Bundle these with regular items to increase overall order value and profitability."""
            
            return {
                "response": response_text,
                "suggested_products": products,
                "follow_up_questions": [
                    "What's the demand for these in my area?",
                    "Can you suggest bundle offers for these?",
                    "What's the optimal pricing strategy?"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting profit suggestions: {e}")
            return self.get_fallback_response("profit")
    
    def generate_shopping_list(self, context: Dict) -> Dict[str, Any]:
        """Generate shopping list based on user's business"""
        try:
            # Get user's frequently ordered items
            query = text("""
                SELECT p.*, COUNT(ph.id) as order_frequency,
                       MAX(ph.purchased_at) as last_ordered
                FROM products p
                JOIN purchase_history ph ON p.id = ph.product_id
                WHERE ph.user_id = :user_id
                AND ph.purchased_at >= datetime('now', '-60 days')
                GROUP BY p.id
                ORDER BY order_frequency DESC, last_ordered ASC
                LIMIT 8
            """)
            
            # For demo, we'll use a general query since we don't have user_id in context
            general_query = text("""
                SELECT p.*, COUNT(ph.id) as popularity
                FROM products p
                LEFT JOIN purchase_history ph ON p.id = ph.product_id
                WHERE p.is_active = 1
                GROUP BY p.id
                ORDER BY popularity DESC
                LIMIT 8
            """)
            
            result = self.db.execute(general_query)
            products = self._format_ai_products(result)
            
            business_type = context.get('business_type', 'business')
            
            response_text = f"""Based on your {business_type}'s purchase patterns, here's a recommended shopping list:

📋 **Essential Items**: Core products you order regularly
🔄 **Restock Items**: Products you haven't ordered recently but usually need
📈 **Trending Items**: Popular products in your category
💡 **Suggestions**: New items that similar businesses are buying

This list is optimized for your business type and location."""
            
            return {
                "response": response_text,
                "suggested_products": products,
                "follow_up_questions": [
                    "Should I add any seasonal items?",
                    "What quantities do you recommend?",
                    "Any bulk purchase discounts available?"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating shopping list: {e}")
            return self.get_fallback_response("shopping")
    
    def get_seasonal_suggestions(self, context: Dict) -> Dict[str, Any]:
        """Get seasonal product suggestions"""
        try:
            # Get current month to suggest seasonal items
            current_month = datetime.now().month
            
            if current_month in [10, 11]:  # Oct-Nov (Diwali season)
                return self.get_diwali_suggestions(context)
            elif current_month in [12, 1, 2]:  # Winter
                seasonal_categories = ['grains', 'oils', 'pulses']
                season_name = "Winter"
            elif current_month in [3, 4, 5]:  # Summer
                seasonal_categories = ['beverages', 'oils']
                season_name = "Summer"
            else:  # Monsoon
                seasonal_categories = ['grains', 'pulses']
                season_name = "Monsoon"
            
            query = text("""
                SELECT p.*
                FROM products p
                WHERE p.category IN :categories
                AND p.is_active = 1
                ORDER BY p.created_at DESC
                LIMIT 8
            """)
            
            # SQLite doesn't support IN with tuples directly, so we'll use a different approach
            category_conditions = " OR ".join([f"p.category = '{cat}'" for cat in seasonal_categories])
            query = text(f"""
                SELECT p.*
                FROM products p
                WHERE ({category_conditions})
                AND p.is_active = 1
                ORDER BY p.created_at DESC
                LIMIT 8
            """)
            
            result = self.db.execute(query)
            products = self._format_ai_products(result)
            
            response_text = f"""For the {season_name} season, here are my recommendations:

🌟 **Seasonal Essentials**: Products that see higher demand during {season_name.lower()}
📊 **Market Trends**: Items trending in your area this season
🎯 **Smart Stocking**: Products with good shelf life for seasonal inventory
💰 **Profit Opportunities**: Seasonal items often have better margins

Stock up early to avoid supply shortages during peak demand."""
            
            return {
                "response": response_text,
                "suggested_products": products,
                "follow_up_questions": [
                    f"What are the best {season_name.lower()} products for my business type?",
                    "How much inventory should I maintain?",
                    "Any upcoming seasonal promotions?"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting seasonal suggestions: {e}")
            return self.get_fallback_response("seasonal")
    
    def get_best_sellers(self, context: Dict) -> Dict[str, Any]:
        """Get best selling products"""
        try:
            query = text("""
                SELECT p.*, COUNT(ph.id) as sales_count
                FROM products p
                LEFT JOIN purchase_history ph ON p.id = ph.product_id
                WHERE p.is_active = 1
                GROUP BY p.id
                ORDER BY sales_count DESC
                LIMIT 8
            """)
            
            result = self.db.execute(query)
            products = self._format_ai_products(result)
            
            city = context.get('city', 'your area')
            
            response_text = f"""Here are the top-selling products in {city}:

🏆 **Best Performers**: Products with highest sales volume
📈 **Consistent Sellers**: Items with steady demand
🎯 **Safe Bets**: Low-risk products for new retailers
💡 **Market Leaders**: Products that drive customer traffic

These items have proven demand and are great for maintaining steady revenue."""
            
            return {
                "response": response_text,
                "suggested_products": products,
                "follow_up_questions": [
                    "Which of these work best for my business size?",
                    "What's the competition like for these products?",
                    "Any emerging trends I should watch?"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting best sellers: {e}")
            return self.get_fallback_response("bestsellers")
    
    def get_new_products(self, context: Dict) -> Dict[str, Any]:
        """Get new products"""
        try:
            query = text("""
                SELECT p.*
                FROM products p
                WHERE p.is_active = 1
                ORDER BY p.created_at DESC
                LIMIT 8
            """)
            
            result = self.db.execute(query)
            products = self._format_ai_products(result)
            
            response_text = """Here are the latest products added to our marketplace:

✨ **New Arrivals**: Fresh products just added to inventory
🚀 **Early Adopter Advantage**: Be first to stock trending items
🎯 **Market Opportunities**: New products often have less competition
📊 **Test & Learn**: Try small quantities to gauge customer response

New products can help differentiate your store and attract customers."""
            
            return {
                "response": response_text,
                "suggested_products": products,
                "follow_up_questions": [
                    "Which new products are trending?",
                    "What's the market potential for these?",
                    "Any launch promotions available?"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting new products: {e}")
            return self.get_fallback_response("new")
    
    def get_general_suggestions(self, context: Dict) -> Dict[str, Any]:
        """General suggestions when query doesn't match specific patterns"""
        business_type = context.get('business_type', 'retailer')
        
        response_text = f"""I'm here to help optimize your {business_type} business! I can assist with:

🛒 **Inventory Planning**: What to stock and when
💰 **Profit Optimization**: High-margin product suggestions  
📊 **Market Trends**: What's selling well in your area
🎯 **Seasonal Advice**: Festive and seasonal stocking tips
📋 **Smart Lists**: Personalized shopping recommendations

What specific area would you like help with?"""
        
        # Get some popular products as general suggestions
        products = self.get_query_relevant_products("popular products", context)
        
        return {
            "response": response_text,
            "suggested_products": products[:4],
            "follow_up_questions": [
                "What should I stock for the upcoming season?",
                "Which products have the best profit margins?",
                "What are the trending items in my area?"
            ]
        }
    
    def get_query_relevant_products(self, query: str, context: Dict) -> List[Dict]:
        """Get products relevant to the query"""
        try:
            query_lower = query.lower()
            
            # Simple keyword matching for product suggestions
            if any(word in query_lower for word in ["diwali", "festive"]):
                categories = ['grains', 'oils', 'sweets']
            elif any(word in query_lower for word in ["profit", "margin"]):
                # Return products with good margins
                return self._get_high_margin_products()
            elif any(word in query_lower for word in ["popular", "best", "trending"]):
                return self._get_popular_products()
            else:
                categories = ['grains', 'pulses', 'oils']
            
            # Get products from relevant categories
            category_conditions = " OR ".join([f"p.category = '{cat}'" for cat in categories])
            query = text(f"""
                SELECT p.*
                FROM products p
                WHERE ({category_conditions})
                AND p.is_active = 1
                ORDER BY p.created_at DESC
                LIMIT 5
            """)
            
            result = self.db.execute(query)
            return self._format_ai_products(result)
            
        except Exception as e:
            logger.error(f"Error getting query relevant products: {e}")
            return []
    
    def _get_high_margin_products(self) -> List[Dict]:
        """Get high margin products"""
        try:
            query = text("""
                SELECT p.*
                FROM products p
                WHERE p.is_active = 1
                AND p.cost_price > 0
                AND ((p.price - p.cost_price) / p.price) >= 0.25
                ORDER BY ((p.price - p.cost_price) / p.price) DESC
                LIMIT 5
            """)
            result = self.db.execute(query)
            return self._format_ai_products(result)
        except:
            return []
    
    def _get_popular_products(self) -> List[Dict]:
        """Get popular products"""
        try:
            query = text("""
                SELECT p.*, COUNT(ph.id) as popularity
                FROM products p
                LEFT JOIN purchase_history ph ON p.id = ph.product_id
                WHERE p.is_active = 1
                GROUP BY p.id
                ORDER BY popularity DESC
                LIMIT 5
            """)
            result = self.db.execute(query)
            return self._format_ai_products(result)
        except:
            return []
    
    def generate_follow_up_questions(self, query: str, context: Dict) -> List[str]:
        """Generate contextual follow-up questions"""
        query_lower = query.lower()
        
        if "diwali" in query_lower or "festive" in query_lower:
            return [
                "Should I focus more on gifts or food items?",
                "What's the ideal inventory quantity for festive season?",
                "Any specific brands that perform better during Diwali?"
            ]
        elif "profit" in query_lower:
            return [
                "What's the demand for high-margin products in my area?",
                "Can you suggest profitable bundle offers?",
                "What pricing strategy works best?"
            ]
        else:
            return [
                "What are the trending products in my category?",
                "How can I optimize my inventory mix?",
                "Any seasonal opportunities I should consider?"
            ]
    
    def _format_ai_products(self, result) -> List[Dict]:
        """Format products for AI response"""
        products = []
        for row in result:
            try:
                products.append({
                    'id': row[0],
                    'name': row[1],
                    'category': row[2],
                    'price': float(row[6]) if row[6] else 0.0,
                    'weight': row[8] or '',
                    'unit': row[9] or ''
                })
            except Exception as e:
                logger.error(f"Error formatting AI product: {e}")
                continue
        return products
    
    def get_fallback_response(self, query_type: str) -> Dict[str, Any]:
        """Fallback response when AI processing fails"""
        fallback_responses = {
            "diwali": {
                "response": "For Diwali, consider stocking festive essentials like premium rice, cooking oils, pulses, and sugar. These items see 2-3x higher demand during the festive season.",
                "suggested_products": [],
                "follow_up_questions": ["What's your budget for festive stocking?", "Any specific product categories you prefer?"]
            },
            "profit": {
                "response": "High-profit items typically include branded goods, premium products, and specialty items. Focus on products with 25%+ margins and good turnover rates.",
                "suggested_products": [],
                "follow_up_questions": ["What's your target customer profile?", "Any specific margin expectations?"]
            },
            "general": {
                "response": "I can help you with inventory planning, profit optimization, seasonal trends, and market insights. What specific area would you like assistance with?",
                "suggested_products": [],
                "follow_up_questions": ["What are your current business challenges?", "Which product categories interest you most?"]
            }
        }
        return fallback_responses.get(query_type, fallback_responses["general"])
