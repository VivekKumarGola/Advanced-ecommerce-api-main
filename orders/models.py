"""
Orders app models for the e-commerce API.
Includes Cart, CartItem, Order, and OrderItem models.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

User = get_user_model()


class Cart(models.Model):
    """
    Shopping cart model to store items before checkout.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts'
        verbose_name = 'Shopping Cart'
        verbose_name_plural = 'Shopping Carts'
    
    def __str__(self):
        return f"Cart for {self.user.email}"
    
    @property
    def total_items(self):
        """
        Calculate total number of items in cart.
        """
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_price(self):
        """
        Calculate total price of all items in cart.
        """
        return sum(item.subtotal for item in self.items.all())
    
    def clear(self):
        """
        Clear all items from cart.
        """
        self.items.all().delete()


class CartItem(models.Model):
    """
    Individual item in a shopping cart.
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = ('cart', 'product')
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name} in {self.cart.user.email}'s cart"
    
    @property
    def subtotal(self):
        """
        Calculate subtotal for this cart item.
        """
        return self.product.price * self.quantity
    
    def save(self, *args, **kwargs):
        """
        Validate quantity doesn't exceed stock.
        """
        if self.quantity > self.product.stock:
            raise ValueError(f"Quantity ({self.quantity}) exceeds available stock ({self.product.stock})")
        super().save(*args, **kwargs)


class Order(models.Model):
    """
    Order model to store completed purchases.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Basic order information (matches database schema)
    id = models.AutoField(primary_key=True)  # Database uses INTEGER, not UUID
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Price breakdown
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Shipping information
    shipping_first_name = models.CharField(max_length=30)
    shipping_last_name = models.CharField(max_length=30)
    shipping_email = models.EmailField()
    shipping_phone = models.CharField(max_length=17, blank=True)
    shipping_address_line_1 = models.CharField(max_length=255)
    shipping_address_line_2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=100, default='USA')
    
    # Billing information  
    billing_same_as_shipping = models.BooleanField(default=True)
    billing_first_name = models.CharField(max_length=30, blank=True)
    billing_last_name = models.CharField(max_length=30, blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=17, blank=True)
    billing_address_line_1 = models.CharField(max_length=255, blank=True)
    billing_address_line_2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    billing_country = models.CharField(max_length=100, default='India')
    
    # Order tracking
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order {self.order_number or f'#{self.id}'} by {self.user.email}"
    
    def save(self, *args, **kwargs):
        """
        Auto-generate order number if not provided.
        """
        if not self.order_number:
            # Generate order number based on ID (will be set after save)
            super().save(*args, **kwargs)
            if not self.order_number:
                self.order_number = f"ORD-{self.id:06d}"
                super().save(update_fields=['order_number'])
        else:
            super().save(*args, **kwargs)
    
    def get_status_display_color(self):
        """
        Get Bootstrap color class for status display.
        """
        status_colors = {
            'pending': 'warning',
            'processing': 'info',
            'shipped': 'primary',
            'delivered': 'success',
            'cancelled': 'danger',
            'refunded': 'secondary',
        }
        return status_colors.get(self.status, 'secondary')
    
    def can_be_cancelled(self):
        """
        Check if order can be cancelled.
        """
        return self.status in ['pending', 'processing']
    
    def total_items(self):
        """
        Calculate total number of items in order.
        """
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    """
    Individual item in an order.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    
    # Store product information at time of order (for historical accuracy)
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_sku = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_items'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        unique_together = ('order', 'product')
    
    def __str__(self):
        return f"{self.quantity}x {self.product_name} in Order {self.order.order_number or f'#{self.order.id}'}"
    
    @property
    def subtotal(self):
        """
        Calculate subtotal for this order item.
        """
        return self.product_price * self.quantity
    
    def save(self, *args, **kwargs):
        """
        Auto-populate product information if not provided.
        """
        if not self.product_name:
            self.product_name = self.product.name
        if not self.product_price:
            self.product_price = self.product.price
        if not self.product_sku:
            self.product_sku = getattr(self.product, 'sku', f'SKU-{self.product.id}')
        
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    """
    Track order status changes for audit trail.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_status_history'
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order {self.order.order_number or f'#{self.order.id}'}: {self.old_status} → {self.new_status}" 