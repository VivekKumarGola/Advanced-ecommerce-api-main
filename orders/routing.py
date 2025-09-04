"""
WebSocket URL routing for orders app.
"""

from django.urls import re_path, path
from . import consumers

websocket_urlpatterns = [
    # Order-specific notifications
    path('ws/orders/', consumers.OrderConsumer.as_asgi()),
    
    # General notifications
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
    
    # Alternative paths with explicit patterns
    re_path(r'ws/orders/$', consumers.OrderConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
] 