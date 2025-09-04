from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Order, OrderItem, Cart, CartItem, OrderStatusHistory
from products.models import Product
from products.serializers import ProductListSerializer

User = get_user_model()


# ============================================================================
# CART SERIALIZERS
# ============================================================================

class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer for cart items with product details
    """
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_id', 'quantity', 
            'total_price', 'added_at', 'updated_at'
        ]
        read_only_fields = ['id', 'added_at', 'updated_at']
    
    def get_total_price(self, obj):
        """Calculate total price for this cart item"""
        return obj.subtotal
    
    def validate_product_id(self, value):
        """Validate product exists and is active"""
        try:
            product = Product.objects.get(id=value, is_active=True)
            if product.stock <= 0:
                raise serializers.ValidationError("Product is out of stock.")
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive.")
    
    def validate_quantity(self, value):
        """Validate quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value
    
    def validate(self, attrs):
        """Validate quantity against product stock"""
        if 'product_id' in attrs and 'quantity' in attrs:
            try:
                product = Product.objects.get(id=attrs['product_id'])
                if attrs['quantity'] > product.stock:
                    raise serializers.ValidationError(
                        f"Only {product.stock} units available in stock."
                    )
            except Product.DoesNotExist:
                pass  # Will be caught by product_id validation
        return attrs


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for shopping cart with items
    """
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = [
            'id', 'items', 'total_items', 'total_price', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_total_items(self, obj):
        """Get total number of items in cart"""
        return obj.total_items
    
    def get_total_price(self, obj):
        """Get total price of all items in cart"""
        return obj.total_price


class AddToCartSerializer(serializers.Serializer):
    """
    Serializer for adding items to cart
    """
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    
    def validate_product_id(self, value):
        """Validate product exists and is active"""
        try:
            product = Product.objects.get(id=value, is_active=True)
            if product.stock <= 0:
                raise serializers.ValidationError("Product is out of stock.")
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive.")
    
    def validate(self, attrs):
        """Validate quantity against product stock"""
        try:
            product = Product.objects.get(id=attrs['product_id'])
            if attrs['quantity'] > product.stock:
                raise serializers.ValidationError({
                    'quantity': f"Only {product.stock} units available in stock."
                })
        except Product.DoesNotExist:
            pass  # Will be caught by product_id validation
        return attrs


class UpdateCartItemSerializer(serializers.Serializer):
    """
    Serializer for updating cart item quantity
    """
    quantity = serializers.IntegerField(min_value=1)
    
    def validate_quantity(self, value):
        """Validate quantity against product stock"""
        cart_item = self.instance
        if cart_item and value > cart_item.product.stock:
            raise serializers.ValidationError(
                f"Only {cart_item.product.stock} units available in stock."
            )
        return value


# ============================================================================
# ORDER SERIALIZERS
# ============================================================================

class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for order items
    """
    product = ProductListSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'quantity', 'product_price', 'total_price'
        ]
    
    def get_total_price(self, obj):
        """Calculate total price for this order item"""
        return obj.subtotal


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for order status history
    """
    class Meta:
        model = OrderStatusHistory
        fields = ['old_status', 'new_status', 'notes', 'created_at']


class OrderListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing user orders
    """
    total_items = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'payment_status',
            'total_price', 'total_items', 'created_at', 'updated_at'
        ]
    
    def get_total_items(self, obj):
        """Get total number of items in order"""
        return obj.total_items


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed order view
    """
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'payment_status',
            'total_price', 'total_items', 'items', 'status_history',
            'shipping_address_line_1', 'shipping_address_line_2',
            'shipping_city', 'shipping_state', 'shipping_postal_code',
            'shipping_country', 'notes', 'created_at', 'updated_at'
        ]
    
    def get_total_items(self, obj):
        """Get total number of items in order"""
        return obj.total_items


class CreateOrderSerializer(serializers.Serializer):
    """
    Serializer for creating orders from cart
    """
    shipping_address_line_1 = serializers.CharField(max_length=255)
    shipping_address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    shipping_city = serializers.CharField(max_length=100)
    shipping_state = serializers.CharField(max_length=100)
    shipping_postal_code = serializers.CharField(max_length=20)
    shipping_country = serializers.CharField(max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate user has items in cart"""
        user = self.context['request'].user
        cart = Cart.objects.filter(user=user).first()
        
        if not cart or not cart.items.exists():
            raise serializers.ValidationError("Cart is empty. Cannot create order.")
        
        # Validate all products are still available and in stock
        for item in cart.items.all():
            if not item.product.is_active:
                raise serializers.ValidationError(
                    f"Product '{item.product.name}' is no longer available."
                )
            if item.quantity > item.product.stock:
                raise serializers.ValidationError(
                    f"Only {item.product.stock} units of '{item.product.name}' available."
                )
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Create order from cart items"""
        user = self.context['request'].user
        cart = Cart.objects.get(user=user)
        
        # Calculate totals
        cart_total = cart.total_price
        
        # Create order
        order = Order.objects.create(
            user=user,
            subtotal=cart_total,
            total_price=cart_total,  # For now, no tax or shipping
            shipping_first_name=user.first_name,
            shipping_last_name=user.last_name,
            shipping_email=user.email,
            shipping_phone=getattr(user, 'phone', ''),
            **validated_data
        )
        
        # Create order items from cart items
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                product_name=cart_item.product.name,
                product_sku=cart_item.product.sku,
                product_price=cart_item.product.price
            )
            
            # Update product stock
            cart_item.product.stock -= cart_item.quantity
            cart_item.product.save(update_fields=['stock'])
        
        # Create initial status history
        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status='pending',
            notes='Order created successfully'
        )
        
        # Clear cart
        cart.items.all().delete()
        
        return order


class UpdateOrderStatusSerializer(serializers.Serializer):
    """
    Serializer for updating order status (Admin only)
    """
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        """Validate status transition is allowed"""
        order = self.instance
        current_status = order.status
        
        # Define allowed status transitions
        allowed_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['shipped', 'cancelled'],
            'shipped': ['delivered', 'returned'],
            'delivered': ['returned'],
            'cancelled': [],  # No transitions from cancelled
            'returned': []   # No transitions from returned
        }
        
        if value not in allowed_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Cannot change status from '{current_status}' to '{value}'"
            )
        
        return value
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update order status and create history entry"""
        old_status = instance.status
        new_status = validated_data['status']
        notes = validated_data.get('notes', '')
        
        # Update order status
        instance.status = new_status
        instance.save(update_fields=['status', 'updated_at'])
        
        # Create status history entry
        OrderStatusHistory.objects.create(
            order=instance,
            old_status=old_status,
            new_status=new_status,
            notes=notes or f'Status changed from {old_status} to {new_status}'
        )
        
        return instance


class UpdatePaymentStatusSerializer(serializers.Serializer):
    """
    Serializer for updating payment status (Admin only)
    """
    payment_status = serializers.ChoiceField(choices=Order.PAYMENT_STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update payment status and create history entry"""
        old_payment_status = instance.payment_status
        new_payment_status = validated_data['payment_status']
        notes = validated_data.get('notes', '')
        
        # Update payment status
        instance.payment_status = new_payment_status
        instance.save(update_fields=['payment_status', 'updated_at'])
        
        # Create status history entry
        OrderStatusHistory.objects.create(
            order=instance,
            old_status=instance.status,  # Keep current order status
            new_status=instance.status,  # Keep current order status
            notes=notes or f'Payment status changed from {old_payment_status} to {new_payment_status}'
        )
        
        return instance


# ============================================================================
# ADMIN SERIALIZERS
# ============================================================================

class AdminOrderListSerializer(serializers.ModelSerializer):
    """
    Serializer for admin order listing with user info
    """
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    total_items = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user_email', 'user_name',
            'status', 'payment_status', 'total_price', 'total_items',
            'created_at', 'updated_at'
        ]
    
    def get_total_items(self, obj):
        """Get total number of items in order"""
        return obj.total_items


class OrderStatsSerializer(serializers.Serializer):
    """
    Serializer for order statistics
    """
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    confirmed_orders = serializers.IntegerField()
    shipped_orders = serializers.IntegerField()
    delivered_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2) 