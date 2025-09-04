"""
WebSocket consumers for real-time order notifications.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class OrderConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for order-related notifications.
    Handles user-specific order updates and admin notifications.
    """
    
    async def connect(self):
        """
        Handle WebSocket connection.
        Authenticate user via JWT token and add to appropriate groups.
        """
        try:
            # Get JWT token from query string
            token = self.scope['query_string'].decode().split('token=')[-1] if 'token=' in self.scope['query_string'].decode() else None
            
            if token:
                # Authenticate user with JWT token
                user = await self.authenticate_jwt_token(token)
                if user and not isinstance(user, AnonymousUser):
                    self.scope['user'] = user
                    await self.accept()
                    
                    # Add user to their personal group
                    self.user_group_name = f'user_{user.id}'
                    await self.channel_layer.group_add(
                        self.user_group_name,
                        self.channel_name
                    )
                    
                    # Add admin users to admin group
                    if user.is_staff or user.is_superuser:
                        await self.channel_layer.group_add(
                            'admins',
                            self.channel_name
                        )
                    
                    # Send connection confirmation
                    await self.send(text_data=json.dumps({
                        'type': 'connection_established',
                        'message': 'Successfully connected to order notifications',
                        'user_id': user.id,
                        'is_admin': user.is_staff or user.is_superuser
                    }))
                    
                    logger.info(f"WebSocket connected for user {user.id} ({user.email})")
                else:
                    await self.close(code=4001)  # Unauthorized
            else:
                await self.close(code=4000)  # Missing token
                
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            await self.close(code=4002)  # Server error
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        Remove user from groups.
        """
        try:
            user = self.scope.get('user')
            if user and not isinstance(user, AnonymousUser):
                # Remove from user group
                user_group_name = f'user_{user.id}'
                await self.channel_layer.group_discard(
                    user_group_name,
                    self.channel_name
                )
                
                # Remove from admin group if applicable
                if user.is_staff or user.is_superuser:
                    await self.channel_layer.group_discard(
                        'admins',
                        self.channel_name
                    )
                
                logger.info(f"WebSocket disconnected for user {user.id} ({user.email})")
        except Exception as e:
            logger.error(f"Error in WebSocket disconnection: {e}")
    
    async def receive(self, text_data):
        """
        Handle messages received from WebSocket.
        Can be used for client-side pings or commands.
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'unknown')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            elif message_type == 'subscribe_order':
                # Client wants to subscribe to specific order updates
                order_id = data.get('order_id')
                if order_id:
                    order_group_name = f'order_{order_id}'
                    await self.channel_layer.group_add(
                        order_group_name,
                        self.channel_name
                    )
                    await self.send(text_data=json.dumps({
                        'type': 'subscription_confirmed',
                        'order_id': order_id
                    }))
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON received in WebSocket")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def order_notification(self, event):
        """
        Handle order notification events from channel layer.
        Send notification to WebSocket client.
        """
        try:
            # Send notification to WebSocket
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'data': event['data']
            }))
            
        except Exception as e:
            logger.error(f"Error sending order notification: {e}")
    
    @database_sync_to_async
    def authenticate_jwt_token(self, token):
        """
        Authenticate JWT token and return user.
        """
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except (InvalidToken, TokenError):
            return AnonymousUser()
        except Exception as e:
            logger.error(f"Error authenticating JWT token: {e}")
            return AnonymousUser()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    General notification consumer for broader application notifications.
    """
    
    async def connect(self):
        """
        Handle WebSocket connection for general notifications.
        """
        try:
            # Get JWT token from query string
            token = self.scope['query_string'].decode().split('token=')[-1] if 'token=' in self.scope['query_string'].decode() else None
            
            if token:
                # Authenticate user with JWT token
                user = await self.authenticate_jwt_token(token)
                if user and not isinstance(user, AnonymousUser):
                    self.scope['user'] = user
                    await self.accept()
                    
                    # Add user to general notifications group
                    await self.channel_layer.group_add(
                        'general_notifications',
                        self.channel_name
                    )
                    
                    # Send connection confirmation
                    await self.send(text_data=json.dumps({
                        'type': 'connection_established',
                        'message': 'Connected to general notifications'
                    }))
                    
                    logger.info(f"General notification WebSocket connected for user {user.id}")
                else:
                    await self.close(code=4001)  # Unauthorized
            else:
                await self.close(code=4000)  # Missing token
                
        except Exception as e:
            logger.error(f"Error in general notification WebSocket connection: {e}")
            await self.close(code=4002)  # Server error
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.
        """
        try:
            # Remove from general notifications group
            await self.channel_layer.group_discard(
                'general_notifications',
                self.channel_name
            )
            
            user = self.scope.get('user')
            if user and not isinstance(user, AnonymousUser):
                logger.info(f"General notification WebSocket disconnected for user {user.id}")
        except Exception as e:
            logger.error(f"Error in general notification WebSocket disconnection: {e}")
    
    async def general_notification(self, event):
        """
        Handle general notification events.
        """
        try:
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'data': event['data']
            }))
        except Exception as e:
            logger.error(f"Error sending general notification: {e}")
    
    @database_sync_to_async
    def authenticate_jwt_token(self, token):
        """
        Authenticate JWT token and return user.
        """
        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except (InvalidToken, TokenError):
            return AnonymousUser()
        except Exception as e:
            logger.error(f"Error authenticating JWT token: {e}")
            return AnonymousUser() 