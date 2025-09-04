import time
import json
import logging
from typing import Any, Optional, List, Union
from functools import wraps
from django.core.cache import cache
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.utils.encoding import force_str

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Centralized cache management system with Redis
    """
    
    # Cache timeout settings (in seconds)
    TIMEOUTS = {
        'short': 300,      # 5 minutes
        'medium': 1800,    # 30 minutes  
        'long': 3600,      # 1 hour
        'very_long': 21600, # 6 hours
        'daily': 86400,    # 24 hours
    }
    
    # Cache key prefixes
    PREFIXES = {
        'product': 'product',
        'category': 'category',
        'user': 'user',
        'order': 'order',
        'cart': 'cart',
        'stats': 'stats',
        'search': 'search',
        'api': 'api',
    }
    
    @classmethod
    def generate_key(cls, prefix: str, *args, **kwargs) -> str:
        """
        Generate a standardized cache key
        """
        key_parts = [cls.PREFIXES.get(prefix, prefix)]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, Model):
                key_parts.append(f"{arg.__class__.__name__}_{arg.pk}")
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments (sorted for consistency)
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}_{v}")
        
        return ":".join(key_parts)
    
    @classmethod
    def get(cls, key: str, default=None) -> Any:
        """
        Get value from cache with error handling
        """
        try:
            return cache.get(key, default)
        except Exception as e:
            # Log as debug instead of error to avoid spam when Redis is unavailable
            logger.debug(f"Cache get skipped for key '{key}': {e}")
            return default
    
    @classmethod
    def set(cls, key: str, value: Any, timeout: Union[str, int] = 'medium') -> bool:
        """
        Set value in cache with error handling
        """
        try:
            if isinstance(timeout, str):
                timeout = cls.TIMEOUTS.get(timeout, cls.TIMEOUTS['medium'])
            
            cache.set(key, value, timeout)
            return True
        except Exception as e:
            # Log as debug instead of error to avoid spam when Redis is unavailable
            logger.debug(f"Cache set skipped for key '{key}': {e}")
            return False
    
    @classmethod
    def delete(cls, key: str) -> bool:
        """
        Delete key from cache
        """
        try:
            cache.delete(key)
            return True
        except Exception as e:
            # Log as debug instead of error to avoid spam when Redis is unavailable
            logger.debug(f"Cache delete skipped for key '{key}': {e}")
            return False
    
    @classmethod
    def delete_pattern(cls, pattern: str) -> int:
        """
        Delete all keys matching a pattern
        """
        try:
            # Check if we're using Redis cache backend
            from django.conf import settings
            cache_backend = settings.CACHES['default']['BACKEND']
            
            if 'redis' in cache_backend.lower():
                # Redis backend - use delete_pattern
                if hasattr(cache, 'delete_pattern'):
                    return cache.delete_pattern(pattern)
                else:
                    # Redis backend but method not available
                    keys = cache.keys(pattern)
                    if keys:
                        cache.delete_many(keys)
                        return len(keys)
                    return 0
            else:
                # Local memory cache - pattern deletion not supported, skip silently
                logger.debug(f"Pattern deletion skipped for non-Redis cache: {pattern}")
                return 0
        except Exception as e:
            # Log as debug instead of error to avoid spam when Redis is unavailable
            logger.debug(f"Cache delete pattern skipped for pattern '{pattern}': {e}")
            return 0
    
    @classmethod
    def invalidate_group(cls, group: str) -> int:
        """
        Invalidate all cache keys for a specific group
        """
        pattern = f"{group}:*"
        return cls.delete_pattern(pattern)
    
    @classmethod
    def get_or_set(cls, key: str, func, timeout: Union[str, int] = 'medium', *args, **kwargs) -> Any:
        """
        Get from cache or set using function result
        """
        value = cls.get(key)
        if value is None:
            try:
                value = func(*args, **kwargs)
                cls.set(key, value, timeout)
            except Exception as e:
                logger.error(f"Cache get_or_set function error for key '{key}': {e}")
                return None
        return value


def cache_result(timeout='medium', key_func=None, invalidate_on=None):
    """
    Decorator for caching function results
    
    Args:
        timeout: Cache timeout ('short', 'medium', 'long', 'very_long', 'daily' or seconds)
        key_func: Function to generate cache key, receives same args as decorated function
        invalidate_on: List of model names that should invalidate this cache when modified
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                for arg in args:
                    if isinstance(arg, Model):
                        key_parts.append(f"{arg.__class__.__name__}_{arg.pk}")
                    else:
                        key_parts.append(str(arg)[:50])  # Limit length
                
                for k, v in sorted(kwargs.items()):
                    key_parts.append(f"{k}_{str(v)[:50]}")
                
                cache_key = ":".join(key_parts)
            
            # Try to get from cache
            result = CacheManager.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            CacheManager.set(cache_key, result, timeout)
            
            return result
        
        # Store metadata for cache invalidation
        wrapper._cache_timeout = timeout
        wrapper._cache_invalidate_on = invalidate_on or []
        
        return wrapper
    return decorator


def invalidate_cache_on_save(sender, instance, **kwargs):
    """
    Signal handler to invalidate cache when models are saved
    """
    model_name = sender.__name__.lower()
    
    # Invalidate model-specific caches
    CacheManager.invalidate_group(model_name)
    
    # Invalidate related caches based on model
    if model_name == 'product':
        CacheManager.invalidate_group('category')  # Products affect category counts
        CacheManager.invalidate_group('search')    # Products affect search results
        CacheManager.invalidate_group('stats')     # Products affect statistics
    
    elif model_name == 'category':
        CacheManager.invalidate_group('product')   # Categories affect product listings
        CacheManager.invalidate_group('search')    # Categories affect search results
    
    elif model_name == 'order':
        CacheManager.invalidate_group('stats')     # Orders affect statistics
        CacheManager.invalidate_group('user')      # Orders affect user stats
    
    elif model_name == 'user':
        CacheManager.invalidate_group('order')     # User changes might affect order displays


def invalidate_cache_on_delete(sender, instance, **kwargs):
    """
    Signal handler to invalidate cache when models are deleted
    """
    # Same logic as save, but for deletions
    invalidate_cache_on_save(sender, instance, **kwargs)


class CacheStatsCollector:
    """
    Collect cache performance statistics
    """
    
    @classmethod
    def get_cache_stats(cls) -> dict:
        """
        Get cache statistics if available
        """
        try:
            # Try to get Redis info if using Redis cache
            if hasattr(cache, '_cache') and hasattr(cache._cache, '_client'):
                client = cache._cache._client
                info = client.info()
                
                return {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory_human', '0B'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'hit_rate': cls._calculate_hit_rate(
                        info.get('keyspace_hits', 0),
                        info.get('keyspace_misses', 0)
                    )
                }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
        
        return {
            'connected_clients': 'N/A',
            'used_memory': 'N/A',
            'keyspace_hits': 'N/A',
            'keyspace_misses': 'N/A',
            'hit_rate': 'N/A'
        }
    
    @classmethod
    def _calculate_hit_rate(cls, hits: int, misses: int) -> str:
        """
        Calculate cache hit rate percentage
        """
        total = hits + misses
        if total == 0:
            return "0%"
        return f"{(hits / total * 100):.2f}%"


# Cache key generators for specific use cases
class CacheKeys:
    """
    Standardized cache key generators
    """
    
    @staticmethod
    def product_list(page=1, category=None, search=None, **filters):
        """Generate cache key for product listings"""
        key_parts = ['product_list', f'page_{page}']
        
        if category:
            key_parts.append(f'cat_{category}')
        if search:
            key_parts.append(f'search_{search[:50]}')
        
        for k, v in sorted(filters.items()):
            key_parts.append(f'{k}_{v}')
        
        return CacheManager.generate_key('api', *key_parts)
    
    @staticmethod
    def product_detail(product_id):
        """Generate cache key for product detail"""
        return CacheManager.generate_key('product', 'detail', product_id)
    
    @staticmethod
    def category_list():
        """Generate cache key for category list"""
        return CacheManager.generate_key('category', 'list')
    
    @staticmethod
    def category_with_counts():
        """Generate cache key for categories with product counts"""
        return CacheManager.generate_key('category', 'with_counts')
    
    @staticmethod
    def user_profile(user_id):
        """Generate cache key for user profile"""
        return CacheManager.generate_key('user', 'profile', user_id)
    
    @staticmethod
    def user_orders(user_id, page=1):
        """Generate cache key for user orders"""
        return CacheManager.generate_key('user', 'orders', user_id, f'page_{page}')
    
    @staticmethod
    def order_stats():
        """Generate cache key for order statistics"""
        return CacheManager.generate_key('stats', 'orders')
    
    @staticmethod
    def search_results(query, page=1, **filters):
        """Generate cache key for search results"""
        key_parts = ['search', query[:50], f'page_{page}']
        
        for k, v in sorted(filters.items()):
            key_parts.append(f'{k}_{v}')
        
        return CacheManager.generate_key('search', *key_parts) 