"""
Django signals for orders app.
Handles WebSocket notifications when order status changes.
"""

import logging
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from utils.cache import CacheManager
from .models import Order

logger = logging.getLogger(__name__)
cache_manager = CacheManager()


@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for Order model post_save.
    Sends WebSocket notifications and clears relevant caches.
    """
    try:
        channel_layer = get_channel_layer()
        
        if channel_layer:
            # Determine the notification type
            if created:
                notification_type = 'order_created'
                message = f'New order {instance.order_number or f"#{instance.id}"} has been placed'
            else:
                notification_type = 'order_updated'
                message = f'Order {instance.order_number or f"#{instance.id}"} status updated to {instance.get_status_display()}'
            
            # Prepare notification data
            notification_data = {
                'type': 'order_notification',
                'data': {
                    'notification_type': notification_type,
                    'order_id': instance.id,
                    'user_id': instance.user.id,
                    'status': instance.status,
                    'status_display': instance.get_status_display(),
                    'total_amount': str(instance.total_price),
                    'message': message,
                    'timestamp': instance.updated_at.isoformat() if instance.updated_at else instance.created_at.isoformat()
                }
            }
            
            # Send notification to user's personal channel
            user_group = f'user_{instance.user.id}'
            async_to_sync(channel_layer.group_send)(
                user_group,
                notification_data
            )
            
            # Send notification to admin group for new orders
            if created:
                admin_notification_data = {
                    'type': 'order_notification',
                    'data': {
                        'notification_type': 'new_order_admin',
                        'order_id': instance.id,
                        'user_email': instance.user.email,
                        'user_name': f"{instance.user.first_name} {instance.user.last_name}".strip() or instance.user.username,
                        'total_amount': str(instance.total_price),
                        'message': f'New order #{instance.id} from {instance.user.email}',
                        'timestamp': instance.created_at.isoformat()
                    }
                }
                
                async_to_sync(channel_layer.group_send)(
                    'admins',
                    admin_notification_data
                )
            
            logger.info(f"WebSocket notification sent for order {instance.id}: {notification_type}")
        
        # Clear order-related caches
        cache_manager.delete_pattern(f'user:{instance.user.id}:orders:*')
        cache_manager.delete_pattern(f'order:{instance.id}:*')
        cache_manager.delete_pattern('orders:admin:*')
        
        # Clear user's cart cache if order was created (cart should be empty now)
        if created:
            cache_manager.delete_pattern(f'user:{instance.user.id}:cart:*')
        
        action = "created" if created else "updated"
        logger.info(f"Order {action}: #{instance.id} for user {instance.user.email}")
        logger.info(f"Cleared order caches for order #{instance.id}")
        
    except Exception as e:
        logger.error(f"Error in order_post_save signal: {e}")


def send_custom_order_notification(order, message, notification_type='custom'):
    """
    Utility function to send custom order notifications.
    Can be used by views or other parts of the application.
    """
    try:
        channel_layer = get_channel_layer()
        
        if channel_layer:
            notification_data = {
                'type': 'order_notification',
                'data': {
                    'notification_type': notification_type,
                    'order_id': order.id,
                    'user_id': order.user.id,
                    'status': order.status,
                    'status_display': order.get_status_display(),
                    'total_amount': str(order.total_amount),
                    'message': message,
                    'timestamp': order.updated_at.isoformat() if order.updated_at else order.created_at.isoformat()
                }
            }
            
            # Send to user
            user_group = f'user_{order.user.id}'
            async_to_sync(channel_layer.group_send)(
                user_group,
                notification_data
            )
            
            logger.info(f"Custom notification sent for order {order.id}: {message}")
        
    except Exception as e:
        logger.error(f"Error sending custom order notification: {e}") 