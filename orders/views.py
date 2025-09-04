from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Sum, Q, F
from django.core.cache import cache
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Cart, CartItem, Order, OrderItem, OrderStatusHistory
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartItemSerializer,
    OrderListSerializer,
    OrderDetailSerializer,
    CreateOrderSerializer,
    UpdateOrderStatusSerializer,
    UpdatePaymentStatusSerializer,
    AdminOrderListSerializer,
    OrderStatsSerializer,
)
from products.models import Product
from products.permissions import IsAdminUser
from utils.cache import CacheManager, CacheKeys, cache_result


# ============================================================================
# CART VIEWS
# ============================================================================

class CartView(APIView):
    """
    Get user's shopping cart
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get user's shopping cart",
        responses={200: CartSerializer}
    )
    def get(self, request):
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class AddToCartView(APIView):
    """
    Add product to cart
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Add product to cart",
        request_body=AddToCartSerializer,
        responses={
            201: CartItemSerializer,
            400: 'Bad Request'
        }
    )
    @transaction.atomic
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']
        
        # Get or create cart
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        # Check if product already in cart
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product_id=product_id,
            defaults={'quantity': quantity}
        )
        
        if not item_created:
            # Update quantity if item already exists
            new_quantity = cart_item.quantity + quantity
            product = Product.objects.get(id=product_id)
            
            if new_quantity > product.stock:
                return Response(
                    {'error': f'Only {product.stock} units available in stock.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            cart_item.quantity = new_quantity
            cart_item.save()
        
        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CartItemView(APIView):
    """
    Update or remove cart item
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self, request, item_id):
        """Get cart item belonging to current user"""
        return get_object_or_404(
            CartItem,
            id=item_id,
            cart__user=request.user
        )
    
    @swagger_auto_schema(
        operation_description="Update cart item quantity",
        request_body=UpdateCartItemSerializer,
        responses={
            200: CartItemSerializer,
            400: 'Bad Request',
            404: 'Not Found'
        }
    )
    def patch(self, request, item_id):
        cart_item = self.get_object(request, item_id)
        
        serializer = UpdateCartItemSerializer(
            cart_item,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        
        cart_item.quantity = serializer.validated_data['quantity']
        cart_item.save()
        
        response_serializer = CartItemSerializer(cart_item)
        return Response(response_serializer.data)
    
    @swagger_auto_schema(
        operation_description="Remove item from cart",
        responses={
            204: 'Item removed successfully',
            404: 'Not Found'
        }
    )
    def delete(self, request, item_id):
        cart_item = self.get_object(request, item_id)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClearCartView(APIView):
    """
    Clear all items from cart
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Clear all items from cart",
        responses={204: 'Cart cleared successfully'}
    )
    def delete(self, request):
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            cart.items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# ORDER VIEWS
# ============================================================================

class OrderListView(generics.ListAPIView):
    """
    List user's orders
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Optimized queryset with select_related"""
        return Order.objects.filter(
            user=self.request.user
        ).select_related('user').order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get list of user's orders",
        responses={200: OrderListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        # Generate cache key for user's orders
        page = request.query_params.get('page', 1)
        cache_key = CacheKeys.user_orders(self.request.user.id, page)
        
        # Try to get from cache
        cached_data = CacheManager.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        response = super().get(request, *args, **kwargs)
        
        # Cache successful response for 10 minutes
        if response.status_code == 200:
            CacheManager.set(cache_key, response.data, 'short')
        
        return response


class OrderDetailView(generics.RetrieveAPIView):
    """
    Get order details
    """
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'order_number'
    
    def get_queryset(self):
        """Optimized queryset with prefetch_related"""
        return Order.objects.filter(user=self.request.user).select_related(
            'user'
        ).prefetch_related(
            'items__product__category',
            'status_history'
        )
    
    @swagger_auto_schema(
        operation_description="Get order details",
        responses={200: OrderDetailSerializer}
    )
    def get(self, request, *args, **kwargs):
        # Generate cache key for this order
        order_number = kwargs.get('order_number')
        cache_key = CacheManager.generate_key('order', 'detail', self.request.user.id, order_number)
        
        # Try to get from cache
        cached_data = CacheManager.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        response = super().get(request, *args, **kwargs)
        
        # Cache successful response for 15 minutes
        if response.status_code == 200:
            CacheManager.set(cache_key, response.data, 'short')
        
        return response


class CreateOrderView(generics.CreateAPIView):
    """
    Create order from cart
    """
    serializer_class = CreateOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Create order from cart items",
        request_body=CreateOrderSerializer,
        responses={
            201: OrderDetailSerializer,
            400: 'Bad Request'
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order = serializer.save()
        
        # Return detailed order information
        response_serializer = OrderDetailSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


# ============================================================================
# ADMIN ORDER VIEWS
# ============================================================================

class AdminOrderListView(generics.ListAPIView):
    """
    List all orders (Admin only)
    """
    serializer_class = AdminOrderListSerializer
    permission_classes = [IsAdminUser]
    queryset = Order.objects.all().select_related('user').order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get list of all orders (Admin only)",
        manual_parameters=[
            openapi.Parameter('status', openapi.IN_QUERY, description="Filter by order status", type=openapi.TYPE_STRING),
            openapi.Parameter('payment_status', openapi.IN_QUERY, description="Filter by payment status", type=openapi.TYPE_STRING),
            openapi.Parameter('user_email', openapi.IN_QUERY, description="Filter by user email", type=openapi.TYPE_STRING),
        ],
        responses={200: AdminOrderListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        payment_status_filter = request.query_params.get('payment_status')
        if payment_status_filter:
            queryset = queryset.filter(payment_status=payment_status_filter)
        
        user_email_filter = request.query_params.get('user_email')
        if user_email_filter:
            queryset = queryset.filter(user__email__icontains=user_email_filter)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AdminOrderDetailView(generics.RetrieveAPIView):
    """
    Get order details (Admin only)
    """
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'order_number'
    queryset = Order.objects.all().prefetch_related(
        'items__product',
        'status_history'
    )
    
    @swagger_auto_schema(
        operation_description="Get order details (Admin only)",
        responses={200: OrderDetailSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UpdateOrderStatusView(generics.UpdateAPIView):
    """
    Update order status (Admin only)
    """
    serializer_class = UpdateOrderStatusSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'order_number'
    queryset = Order.objects.all()
    
    @swagger_auto_schema(
        operation_description="Update order status (Admin only)",
        request_body=UpdateOrderStatusSerializer,
        responses={
            200: OrderDetailSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def patch(self, request, *args, **kwargs):
        order = self.get_object()
        serializer = self.get_serializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_order = serializer.save()
        
        # Return updated order details
        response_serializer = OrderDetailSerializer(updated_order)
        return Response(response_serializer.data)


class UpdatePaymentStatusView(generics.UpdateAPIView):
    """
    Update payment status (Admin only)
    """
    serializer_class = UpdatePaymentStatusSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'order_number'
    queryset = Order.objects.all()
    
    @swagger_auto_schema(
        operation_description="Update payment status (Admin only)",
        request_body=UpdatePaymentStatusSerializer,
        responses={
            200: OrderDetailSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def patch(self, request, *args, **kwargs):
        order = self.get_object()
        serializer = self.get_serializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_order = serializer.save()
        
        # Return updated order details
        response_serializer = OrderDetailSerializer(updated_order)
        return Response(response_serializer.data)


# ============================================================================
# UTILITY VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def order_statistics(request):
    """
    Get order statistics (Admin only)
    """
    cache_key = CacheKeys.order_stats()
    cached_data = CacheManager.get(cache_key)
    
    if cached_data is not None:
        return Response(cached_data)
    
    # Calculate statistics with optimized queries
    total_orders = Order.objects.count()
    
    # Count orders by status
    status_counts = Order.objects.aggregate(
        pending_orders=Count('id', filter=Q(status='pending')),
        confirmed_orders=Count('id', filter=Q(status='confirmed')),
        shipped_orders=Count('id', filter=Q(status='shipped')),
        delivered_orders=Count('id', filter=Q(status='delivered')),
        cancelled_orders=Count('id', filter=Q(status='cancelled')),
    )
    
    # Calculate revenue (exclude cancelled orders)
    revenue_stats = Order.objects.exclude(status='cancelled').aggregate(
        total_revenue=Sum('total_price') or 0
    )
    
    # Calculate average order value
    average_order_value = 0
    if total_orders > 0:
        average_order_value = revenue_stats['total_revenue'] / total_orders
    
    stats_data = {
        'total_orders': total_orders,
        'total_revenue': revenue_stats['total_revenue'],
        'average_order_value': round(average_order_value, 2),
        **status_counts
    }
    
    serializer = OrderStatsSerializer(stats_data)
    
    # Cache for 30 minutes
    CacheManager.set(cache_key, serializer.data, 'medium')
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def recent_orders(request):
    """
    Get recent orders (Admin only)
    """
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:10]
    serializer = AdminOrderListSerializer(recent_orders, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def pending_orders(request):
    """
    Get pending orders (Admin only)
    """
    pending = Order.objects.filter(status='pending').select_related('user').order_by('-created_at')
    serializer = AdminOrderListSerializer(pending, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_order_summary(request):
    """
    Get user's order summary
    """
    user = request.user
    
    # Get user's order statistics
    user_stats = Order.objects.filter(user=user).aggregate(
        total_orders=Count('id'),
        total_spent=Sum('total_price') or 0,
        pending_orders=Count('id', filter=Q(status='pending')),
        delivered_orders=Count('id', filter=Q(status='delivered')),
    )
    
    # Get recent orders
    recent_orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
    recent_orders_data = OrderListSerializer(recent_orders, many=True).data
    
    return Response({
        'statistics': user_stats,
        'recent_orders': recent_orders_data
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_update_order_status(request):
    """
    Bulk update order status (Admin only)
    """
    order_ids = request.data.get('order_ids', [])
    new_status = request.data.get('status')
    notes = request.data.get('notes', '')
    
    if not order_ids or not new_status:
        return Response(
            {'error': 'order_ids and status are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate status
    valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return Response(
            {'error': f'Invalid status. Must be one of: {valid_statuses}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    updated_orders = []
    errors = []
    
    with transaction.atomic():
        for order_id in order_ids:
            try:
                order = Order.objects.get(id=order_id)
                
                # Update status
                old_status = order.status
                order.status = new_status
                order.save(update_fields=['status', 'updated_at'])
                
                # Create status history
                OrderStatusHistory.objects.create(
                    order=order,
                    old_status=old_status,
                    new_status=new_status,
                    notes=notes or f'Bulk status change from {old_status} to {new_status}'
                )
                
                updated_orders.append(order_id)
                
            except Order.DoesNotExist:
                errors.append(f'Order {order_id} not found')
            except Exception as e:
                errors.append(f'Error updating order {order_id}: {str(e)}')
    
    return Response({
        'updated_orders': updated_orders,
        'errors': errors,
        'total_updated': len(updated_orders)
    })
