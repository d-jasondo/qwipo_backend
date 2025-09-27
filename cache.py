import json
import time
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

class SimpleCache:
    """Simple in-memory cache implementation"""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if key in self._cache:
                # Check if expired
                if key in self._timestamps:
                    if time.time() - self._timestamps[key]['created'] > self._timestamps[key]['ttl']:
                        self.delete(key)
                        return None
                return self._cache[key]
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL (time to live) in seconds"""
        try:
            self._cache[key] = value
            self._timestamps[key] = {
                'created': time.time(),
                'ttl': ttl
            }
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if key in self._cache:
                del self._cache[key]
            if key in self._timestamps:
                del self._timestamps[key]
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all cache"""
        try:
            self._cache.clear()
            self._timestamps.clear()
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    def cleanup_expired(self):
        """Remove expired entries"""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, timestamp_info in self._timestamps.items():
                if current_time - timestamp_info['created'] > timestamp_info['ttl']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self.delete(key)
                
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")

# Global cache instance
cache = SimpleCache()

# For production, you might want to use Redis
# import redis
# import os
# 
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# 
# class RedisCache:
#     def __init__(self):
#         self.redis_client = redis.from_url(REDIS_URL)
#     
#     def get(self, key: str) -> Optional[Any]:
#         try:
#             value = self.redis_client.get(key)
#             if value:
#                 return json.loads(value)
#             return None
#         except Exception as e:
#             logger.error(f"Redis get error: {e}")
#             return None
#     
#     def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
#         try:
#             self.redis_client.setex(key, ttl, json.dumps(value, default=str))
#             return True
#         except Exception as e:
#             logger.error(f"Redis set error: {e}")
#             return False
#     
#     def delete(self, key: str) -> bool:
#         try:
#             self.redis_client.delete(key)
#             return True
#         except Exception as e:
#             logger.error(f"Redis delete error: {e}")
#             return False
# 
# # Uncomment for Redis usage
# # cache = RedisCache()
