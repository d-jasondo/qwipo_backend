# import pandas as pd
# import numpy as np
# from sklearn.metrics.pairwise import cosine_similarity
# from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
import logging
from cache import cache
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedRecommendationEngine:
    def __init__(self, db: Session):
        self.db = db
        # cache keys for computed matrices
        self._cbf_cache_key = "cbf_matrix_v1"
        self._cf_cache_key = "cf_item_sim_v1"
    
    def get_homepage_recommendations(self, user_id: int) -> Dict[str, Any]:
        """Get all recommendations for homepage based on your design"""
        cache_key = f"homepage_{user_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            # 1. Personalized recommendations (Top Picks for Your Store)
            personalized = self.get_personalized_recommendations(user_id, limit=8)
            
            # 2. Daily deals and promotions
            daily_deals = self.get_daily_deals(user_id, limit=6)
            
            # 3. Trending in area
            trending = self.get_trending_in_area(user_id, limit=6)
            
            # 4. Low stock alerts (based on user's purchase history)
            low_stock = self.get_low_stock_alerts(user_id, limit=4)
            
            # 5. Seasonal deals
            seasonal = self.get_seasonal_deals()
            
            response = {
                "personalized_recommendations": personalized,
                "daily_deals": daily_deals,
                "trending_products": trending,
                "low_stock_alerts": low_stock,
                "seasonal_deals": seasonal
            }
            
            cache.set(cache_key, response, 900)  # Cache for 15 minutes
            return response
            
        except Exception as e:
            logger.error(f"Error generating homepage recommendations: {e}")
            return self.get_fallback_recommendations()
    
    def get_personalized_recommendations(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Based on past orders and local trends"""
        try:
            # Get user's business type and location
            user_query = text("SELECT business_type, city FROM users WHERE id = :user_id")
            user_result = self.db.execute(user_query, {'user_id': user_id})
            user_data = user_result.fetchone()
            
            if not user_data:
                return self.get_popular_products(limit)
            
            business_type, city = user_data
            
            # Get products based on similar businesses and location
            query = text("""
                SELECT p.*, 
                       COUNT(ph.id) as purchase_count,
                       COUNT(DISTINCT ph.user_id) as unique_buyers
                FROM products p
                LEFT JOIN purchase_history ph ON p.id = ph.product_id 
                    AND ph.purchased_at >= datetime('now', '-30 days')
                LEFT JOIN users u ON ph.user_id = u.id
                WHERE p.is_active = 1
                AND (u.business_type = :business_type OR u.city = :city)
                GROUP BY p.id
                ORDER BY purchase_count DESC, unique_buyers DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {
                'business_type': business_type,
                'city': city,
                'limit': limit
            })
            
            return self._format_products(result)
            
        except Exception as e:
            logger.error(f"Error in personalized recommendations: {e}")
            return self.get_popular_products(limit)
    
    def get_daily_deals(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get daily deals and promotions"""
        try:
            query = text("""
                SELECT p.*, dp.title as deal_title, dp.discount_value
                FROM products p
                JOIN deal_promotions dp ON p.id = dp.product_id
                WHERE dp.is_active = 1 
                AND dp.valid_from <= datetime('now') 
                AND dp.valid_until >= datetime('now')
                AND p.is_active = 1
                ORDER BY dp.discount_value DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {'limit': limit})
            return self._format_products(result)
            
        except Exception as e:
            logger.error(f"Error getting daily deals: {e}")
            return []
    
    def get_trending_in_area(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get products trending in user's city/area"""
        try:
            # Get user's city
            user_query = text("SELECT city FROM users WHERE id = :user_id")
            user_result = self.db.execute(user_query, {'user_id': user_id})
            user_city = user_result.scalar()
            
            if not user_city:
                return self.get_popular_products(limit)
            
            query = text("""
                SELECT p.*, COUNT(ph.id) as recent_purchases
                FROM products p
                JOIN purchase_history ph ON p.id = ph.product_id
                JOIN users u ON ph.user_id = u.id
                WHERE ph.purchased_at >= datetime('now', '-7 days')
                AND u.city = :city
                AND p.is_active = 1
                GROUP BY p.id
                ORDER BY recent_purchases DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {'city': user_city, 'limit': limit})
            return self._format_products(result)
            
        except Exception as e:
            logger.error(f"Error getting trending products: {e}")
            return self.get_popular_products(limit)
    
    def get_low_stock_alerts(self, user_id: int, limit: int = 5) -> List[Dict]:
        """Get products that user frequently buys but might be running low on"""
        try:
            query = text("""
                SELECT p.*, COUNT(ph.id) as user_purchase_count,
                       MAX(ph.purchased_at) as last_purchase
                FROM products p
                JOIN purchase_history ph ON p.id = ph.product_id
                WHERE ph.user_id = :user_id
                AND ph.purchased_at >= datetime('now', '-90 days')
                AND p.is_active = 1
                GROUP BY p.id
                HAVING MAX(ph.purchased_at) <= datetime('now', '-15 days')
                ORDER BY user_purchase_count DESC, last_purchase ASC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {'user_id': user_id, 'limit': limit})
            return self._format_products(result)
            
        except Exception as e:
            logger.error(f"Error getting low stock alerts: {e}")
            return []
    
    def get_seasonal_deals(self) -> List[Dict[str, Any]]:
        """Get seasonal deals and promotions"""
        try:
            # Mock seasonal deals - in production, this would be more sophisticated
            seasonal_deals = [
                {
                    "title": "Diwali Special Offers",
                    "description": "Up to 30% off on festive essentials",
                    "banner_image": "/images/diwali-banner.jpg",
                    "valid_until": "2024-11-15",
                    "categories": ["sweets", "snacks", "decorations"]
                },
                {
                    "title": "Winter Essentials",
                    "description": "Stock up for the winter season",
                    "banner_image": "/images/winter-banner.jpg",
                    "valid_until": "2024-12-31",
                    "categories": ["grains", "pulses", "oils"]
                }
            ]
            return seasonal_deals
        except Exception as e:
            logger.error(f"Error getting seasonal deals: {e}")
            return []
    
    def get_product_page_recommendations(self, product_id: int, user_id: int) -> Dict[str, Any]:
        """Recommendations for product detail page (combo offers, related products)"""
        cache_key = f"product_page_{product_id}_{user_id}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            # 1. Similar products
            similar = self.get_similar_products(product_id, limit=4)
            
            # 2. Frequently bought together
            combo_offers = self.get_frequently_bought_together(product_id, limit=2)
            
            # 3. New products in same category
            new_products = self.get_new_products_in_category(product_id, limit=4)
            
            response = {
                "similar_products": similar,
                "combo_offers": combo_offers,
                "new_products": new_products
            }
            
            cache.set(cache_key, response, 1800)  # Cache for 30 minutes
            return response
            
        except Exception as e:
            logger.error(f"Error in product page recommendations: {e}")
            return {"similar_products": [], "combo_offers": [], "new_products": []}
    
    def get_similar_products(self, product_id: int, limit: int = 4) -> List[Dict]:
        """Get products similar to the given product"""
        try:
            # Get the product's category and subcategory
            product_query = text("SELECT category, subcategory FROM products WHERE id = :product_id")
            product_result = self.db.execute(product_query, {'product_id': product_id})
            product_data = product_result.fetchone()
            
            if not product_data:
                return []
            
            category, subcategory = product_data
            
            query = text("""
                SELECT p.*
                FROM products p
                WHERE p.id != :product_id
                AND p.is_active = 1
                AND (p.category = :category OR p.subcategory = :subcategory)
                ORDER BY 
                    CASE WHEN p.subcategory = :subcategory THEN 1 ELSE 2 END,
                    p.created_at DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {
                'product_id': product_id,
                'category': category,
                'subcategory': subcategory,
                'limit': limit
            })
            
            return self._format_products(result)
            
        except Exception as e:
            logger.error(f"Error getting similar products: {e}")
            return []
    
    def get_frequently_bought_together(self, product_id: int, limit: int = 3) -> List[Dict]:
        """Get products frequently bought together (for combo offers)"""
        try:
            query = text("""
                SELECT p2.*, COUNT(*) as combo_count
                FROM purchase_history ph1
                JOIN purchase_history ph2 ON ph1.order_id = ph2.order_id 
                    AND ph1.product_id != ph2.product_id
                JOIN products p2 ON ph2.product_id = p2.id
                WHERE ph1.product_id = :product_id
                AND p2.is_active = 1
                GROUP BY p2.id
                ORDER BY combo_count DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {'product_id': product_id, 'limit': limit})
            return self._format_products(result)
            
        except Exception as e:
            logger.error(f"Error getting frequently bought together: {e}")
            return []
    
    def get_new_products_in_category(self, product_id: int, limit: int = 4) -> List[Dict]:
        """Get new products in the same category"""
        try:
            # Get the product's category
            product_query = text("SELECT category FROM products WHERE id = :product_id")
            product_result = self.db.execute(product_query, {'product_id': product_id})
            category = product_result.scalar()
            
            if not category:
                return []
            
            query = text("""
                SELECT p.*
                FROM products p
                WHERE p.id != :product_id
                AND p.category = :category
                AND p.is_active = 1
                ORDER BY p.created_at DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {
                'product_id': product_id,
                'category': category,
                'limit': limit
            })
            
            return self._format_products(result)
            
        except Exception as e:
            logger.error(f"Error getting new products in category: {e}")
            return []
    
    def _format_products(self, result) -> List[Dict]:
        """Format SQL result to product dictionary"""
        products = []
        for row in result:
            try:
                product = {
                    'id': row[0],
                    'name': row[1],
                    'category': row[2],
                    'price': float(row[6]) if row[6] else 0.0,
                    'original_price': float(row[7]) if row[7] else None,
                    'discount_percent': row[13] or 0,
                    'weight': row[8] or '',
                    'unit': row[9] or '',
                    'image_url': row[17],
                    'is_deal': bool(row[12]) if row[12] is not None else False,
                    'cashback_offer': row[14] or 0,
                    'is_combo': bool(row[15]) if row[15] is not None else False
                }
                
                # Calculate discount percent if not provided
                if product['original_price'] and product['original_price'] > product['price']:
                    product['discount_percent'] = round(
                        (product['original_price'] - product['price']) / product['original_price'] * 100, 1
                    )
                
                products.append(product)
            except Exception as e:
                logger.error(f"Error formatting product row: {e}")
                continue
                
        return products
    
    def get_popular_products(self, limit: int = 10) -> List[Dict]:
        """Fallback to popular products"""
        try:
            query = text("""
                SELECT p.*, COUNT(ph.id) as purchase_count
                FROM products p
                LEFT JOIN purchase_history ph ON p.id = ph.product_id
                WHERE p.is_active = 1
                GROUP BY p.id
                ORDER BY purchase_count DESC, p.created_at DESC
                LIMIT :limit
            """)
            result = self.db.execute(query, {'limit': limit})
            return self._format_products(result)
        except Exception as e:
            logger.error(f"Error getting popular products: {e}")
            return []
    
    def get_fallback_recommendations(self) -> Dict[str, Any]:
        """Complete fallback when everything fails"""
        popular = self.get_popular_products(20)
        return {
            "personalized_recommendations": popular[:8] if len(popular) >= 8 else popular,
            "daily_deals": popular[8:14] if len(popular) >= 14 else popular[:6] if len(popular) >= 6 else popular,
            "trending_products": popular[14:20] if len(popular) >= 20 else popular[:6] if len(popular) >= 6 else popular,
            "low_stock_alerts": [],
            "seasonal_deals": self.get_seasonal_deals()
        }

    # ----------------------------
    # Content-Based Filtering (CBF)
    # ----------------------------
    def _build_cbf_matrix(self):
        """Build TF-IDF matrix for products using textual attributes."""
        cached = cache.get(self._cbf_cache_key)
        if cached:
            return cached
        query = text(
            """
            SELECT id, name, category, COALESCE(subcategory, ''), COALESCE(brand, ''), COALESCE(description, '')
            FROM products
            WHERE is_active = 1
            """
        )
        rows = self.db.execute(query).fetchall()
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=["id", "name", "category", "subcategory", "brand", "description"])
        df["text"] = (
            df["name"].astype(str) + " " +
            df["category"].astype(str) + " " +
            df["subcategory"].astype(str) + " " +
            df["brand"].astype(str) + " " +
            df["description"].astype(str)
        )
        tfidf = TfidfVectorizer(stop_words="english")
        matrix = tfidf.fit_transform(df["text"].fillna(""))
        result = {"df": df, "matrix": matrix, "tfidf": tfidf}
        cache.set(self._cbf_cache_key, result, 3600)
        return result

    def get_content_based_recommendations(self, product_id: int, limit: int = 10) -> List[Dict]:
        """Products similar to given product via TF-IDF cosine similarity."""
        data = self._build_cbf_matrix()
        if not data:
            return []
        df = data["df"]
        matrix = data["matrix"]
        # find index of product
        idx_list = df.index[df["id"] == product_id].tolist()
        if not idx_list:
            return []
        idx = idx_list[0]
        sims = cosine_similarity(matrix[idx], matrix).ravel()
        df = df.copy()
        df["score"] = sims
        top_ids = df[df["id"] != product_id].nlargest(limit, "score")["id"].tolist()
        if not top_ids:
            return []
        ids_csv = ",".join(str(i) for i in top_ids)
        res = self.db.execute(text(f"SELECT * FROM products WHERE id IN ({ids_csv})"))
        return self._format_products(res)

    # ----------------------------
    # Collaborative Filtering (Item-based)
    # ----------------------------
    def _build_cf_item_similarity(self):
        cached = cache.get(self._cf_cache_key)
        if cached:
            return cached
        q = text(
            """
            SELECT user_id, product_id, SUM(quantity) as qty
            FROM purchase_history
            GROUP BY user_id, product_id
            """
        )
        rows = self.db.execute(q).fetchall()
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=["user_id", "product_id", "qty"])
        pivot = df.pivot_table(index="user_id", columns="product_id", values="qty", fill_value=0)
        if pivot.shape[1] == 0:
            return None
        item_sim = cosine_similarity(pivot.T)
        item_ids = list(pivot.columns)
        result = {"item_sim": item_sim, "item_ids": item_ids, "pivot": pivot}
        cache.set(self._cf_cache_key, result, 1800)
        return result

    def get_collaborative_recommendations(self, user_id: int, limit: int = 10) -> List[Dict]:
        data = self._build_cf_item_similarity()
        if not data:
            return self.get_popular_products(limit)
        item_sim = data["item_sim"]
        item_ids = data["item_ids"]
        pivot = data["pivot"]
        if user_id not in pivot.index:
            return self.get_popular_products(limit)
        user_vector = pivot.loc[user_id].values
        scores = user_vector @ item_sim
        # Exclude already purchased items
        already_idxs = np.where(user_vector > 0)[0]
        scores[already_idxs] = -np.inf
        top_idx = np.argsort(scores)[::-1][:limit]
        rec_ids = [item_ids[i] for i in top_idx if np.isfinite(scores[i])]
        if not rec_ids:
            return self.get_popular_products(limit)
        ids_csv = ",".join(str(i) for i in rec_ids)
        res = self.db.execute(text(f"SELECT * FROM products WHERE id IN ({ids_csv})"))
        return self._format_products(res)

    # ----------------------------
    # Hybrid (CBF + CF)
    # ----------------------------
    def get_hybrid_recommendations(self, user_id: int, limit: int = 10, alpha: float = 0.6) -> List[Dict]:
        """Blend CF and CBF scores. alpha weights CF; (1-alpha) weights CBF."""
        # CF candidates
        cf_list = self.get_collaborative_recommendations(user_id, limit=50)
        cf_rank = {p["id"]: (len(cf_list) - i) / max(1, len(cf_list)) for i, p in enumerate(cf_list)} if cf_list else {}
        # Seed products from user's recent purchases for CBF expansion
        seed_q = text(
            """
            SELECT product_id FROM purchase_history
            WHERE user_id = :uid
            ORDER BY purchased_at DESC
            LIMIT 5
            """
        )
        seeds = [r[0] for r in self.db.execute(seed_q, {"uid": user_id}).fetchall()]
        cbf_scores: Dict[int, float] = {}
        for pid in seeds:
            sims = self.get_content_based_recommendations(pid, limit=50)
            for rank, p in enumerate(sims):
                cbf_scores[p["id"]] = max(cbf_scores.get(p["id"], 0.0), (50 - rank) / 50)
        # Blend scores
        all_ids = set(cbf_scores.keys()) | set(cf_rank.keys())
        blended = []
        for pid in all_ids:
            score = alpha * cf_rank.get(pid, 0.0) + (1 - alpha) * cbf_scores.get(pid, 0.0)
            blended.append((pid, score))
        blended.sort(key=lambda x: x[1], reverse=True)
        rec_ids = [pid for pid, _ in blended[:limit]]
        if not rec_ids:
            return self.get_popular_products(limit)
        ids_csv = ",".join(str(i) for i in rec_ids)
        res = self.db.execute(text(f"SELECT * FROM products WHERE id IN ({ids_csv})"))
        return self._format_products(res)
