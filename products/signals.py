"""
Django signals for products app.
Handles cache invalidation when product data changes.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from utils.cache import CacheManager
from .models import Product, Category

logger = logging.getLogger(__name__)
cache_manager = CacheManager()


@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for Product model post_save.
    Invalidates relevant caches when a product is created or updated.
    """
    try:
        # Clear product-related caches
        cache_manager.delete_pattern('products:*')
        cache_manager.delete_pattern('product:*')
        
        # Clear category caches (product count might have changed)
        cache_manager.delete_pattern('categories:*')
        cache_manager.delete_pattern('category:*')
        
        # Clear specific product cache
        cache_manager.delete(f'product:detail:{instance.id}')
        cache_manager.delete(f'product:detail:{instance.slug}')
        
        # Clear category-specific product lists
        if instance.category:
            cache_manager.delete_pattern(f'products:category:{instance.category.slug}:*')
            cache_manager.delete_pattern(f'products:category:{instance.category.id}:*')
        
        action = "created" if created else "updated"
        logger.info(f"Product {action}: {instance.name} (ID: {instance.id})")
        logger.info(f"Cleared product and category caches for product: {instance.name}")
        
    except Exception as e:
        logger.error(f"Error in product_post_save signal: {e}")


@receiver(post_delete, sender=Product)
def product_post_delete(sender, instance, **kwargs):
    """
    Signal handler for Product model post_delete.
    Invalidates relevant caches when a product is deleted.
    """
    try:
        # Clear product-related caches
        cache_manager.delete_pattern('products:*')
        cache_manager.delete_pattern('product:*')
        
        # Clear category caches (product count might have changed)
        cache_manager.delete_pattern('categories:*')
        cache_manager.delete_pattern('category:*')
        
        # Clear specific product cache
        cache_manager.delete(f'product:detail:{instance.id}')
        cache_manager.delete(f'product:detail:{instance.slug}')
        
        # Clear category-specific product lists
        if instance.category:
            cache_manager.delete_pattern(f'products:category:{instance.category.slug}:*')
            cache_manager.delete_pattern(f'products:category:{instance.category.id}:*')
        
        logger.info(f"Product deleted: {instance.name} (ID: {instance.id})")
        logger.info(f"Cleared product and category caches for deleted product: {instance.name}")
        
    except Exception as e:
        logger.error(f"Error in product_post_delete signal: {e}")


@receiver(post_save, sender=Category)
def category_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for Category model post_save.
    Invalidates relevant caches when a category is created or updated.
    """
    try:
        # Clear category-related caches
        cache_manager.delete_pattern('categories:*')
        cache_manager.delete_pattern('category:*')
        
        # Clear specific category cache
        cache_manager.delete(f'category:detail:{instance.id}')
        cache_manager.delete(f'category:detail:{instance.slug}')
        
        # Clear product lists for this category
        cache_manager.delete_pattern(f'products:category:{instance.slug}:*')
        cache_manager.delete_pattern(f'products:category:{instance.id}:*')
        
        action = "created" if created else "updated"
        logger.info(f"Category {action}: {instance.name} (ID: {instance.id})")
        logger.info(f"Cleared category and product caches for category: {instance.name}")
        
    except Exception as e:
        logger.error(f"Error in category_post_save signal: {e}")


@receiver(post_delete, sender=Category)
def category_post_delete(sender, instance, **kwargs):
    """
    Signal handler for Category model post_delete.
    Invalidates relevant caches when a category is deleted.
    """
    try:
        # Clear category-related caches
        cache_manager.delete_pattern('categories:*')
        cache_manager.delete_pattern('category:*')
        
        # Clear specific category cache
        cache_manager.delete(f'category:detail:{instance.id}')
        cache_manager.delete(f'category:detail:{instance.slug}')
        
        # Clear product lists for this category
        cache_manager.delete_pattern(f'products:category:{instance.slug}:*')
        cache_manager.delete_pattern(f'products:category:{instance.id}:*')
        
        # Clear all product caches since category relationships changed
        cache_manager.delete_pattern('products:*')
        
        logger.info(f"Category deleted: {instance.name} (ID: {instance.id})")
        logger.info(f"Cleared all caches for deleted category: {instance.name}")
        
    except Exception as e:
        logger.error(f"Error in category_post_delete signal: {e}") 