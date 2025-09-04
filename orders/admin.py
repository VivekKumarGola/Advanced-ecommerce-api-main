"""
Django admin configuration for Orders app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum
from .models import Cart, CartItem, Order, OrderItem, OrderStatusHistory


class CartItemInline(admin.TabularInline):
    """
    Inline admin for CartItem model.
    """
    model = CartItem
    extra = 0
    readonly_fields = ('subtotal', 'added_at')
    fields = ('product', 'quantity', 'subtotal', 'added_at')
    
    def subtotal(self, obj):
        if obj.pk:
            return f"${obj.subtotal:.2f}"
        return "-"
    subtotal.short_description = 'Subtotal'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Admin configuration for Cart model.
    """
    list_display = ('user', 'total_items', 'total_price_display', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('total_items', 'total_price_display', 'created_at', 'updated_at')
    ordering = ('-updated_at',)
    inlines = [CartItemInline]
    
    fieldsets = (
        ('Cart Information', {
            'fields': ('user', 'total_items', 'total_price_display')
        }),
        ('Meta Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_price_display(self, obj):
        return f"${obj.total_price:.2f}"
    total_price_display.short_description = 'Total Price'
    total_price_display.admin_order_field = 'total_price'


class OrderItemInline(admin.TabularInline):
    """
    Inline admin for OrderItem model.
    """
    model = OrderItem
    extra = 0
    readonly_fields = ('subtotal', 'product_name', 'product_price', 'product_sku')
    fields = ('product', 'product_name', 'product_sku', 'quantity', 'product_price', 'subtotal')
    
    def subtotal(self, obj):
        if obj.pk:
            return f"${obj.subtotal:.2f}"
        return "-"
    subtotal.short_description = 'Subtotal'


class OrderStatusHistoryInline(admin.TabularInline):
    """
    Inline admin for OrderStatusHistory model.
    """
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'created_at', 'changed_by')
    fields = ('old_status', 'new_status', 'changed_by', 'notes', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin configuration for Order model.
    """
    list_display = (
        'order_number_display', 'user', 'status_badge', 'payment_status_badge', 'total_price_display', 
        'created_at'
    )
    list_filter = (
        'status', 'payment_status', 'created_at', 'updated_at',
        'shipping_country', 'shipping_state'
    )
    search_fields = (
        'order_number', 'user__email', 'user__first_name', 'user__last_name',
        'shipping_email', 'shipping_first_name', 'shipping_last_name'
    )
    readonly_fields = (
        'order_number', 'subtotal', 'total_price', 'created_at', 'updated_at',
        'order_summary'
    )
    ordering = ('-created_at',)
    list_per_page = 25
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'status', 'payment_status')
        }),
        ('Order Summary', {
            'fields': ('order_summary', 'subtotal', 'total_price')
        }),
        ('Shipping Information', {
            'fields': (
                ('shipping_first_name', 'shipping_last_name'),
                'shipping_email', 'shipping_phone',
                'shipping_address_line_1', 'shipping_address_line_2',
                ('shipping_city', 'shipping_state', 'shipping_postal_code'),
                'shipping_country'
            )
        }),
        ('Billing Information', {
            'fields': (
                'billing_same_as_shipping',
                ('billing_first_name', 'billing_last_name'),
                'billing_email', 'billing_phone',
                'billing_address_line_1', 'billing_address_line_2',
                ('billing_city', 'billing_state', 'billing_postal_code'),
                'billing_country'
            ),
            'classes': ('collapse',)
        }),
        ('Meta Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_processing', 'mark_as_shipped', 'mark_as_delivered', 'mark_as_cancelled']
    

    
    def order_number_display(self, obj):
        """Display order number with link to detail."""
        return obj.order_number or f"#{obj.id}"
    order_number_display.short_description = 'Order Number'
    order_number_display.admin_order_field = 'order_number'
    
    def status_badge(self, obj):
        """Display order status with color coding."""
        colors = {
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'shipped': '#007bff',
            'delivered': '#28a745',
            'cancelled': '#dc3545',
            'refunded': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def payment_status_badge(self, obj):
        """Display payment status with color coding."""
        colors = {
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545',
            'refunded': '#6c757d'
        }
        color = colors.get(obj.payment_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment Status'
    payment_status_badge.admin_order_field = 'payment_status'
    
    def total_price_display(self, obj):
        return f"${obj.total_price:.2f}"
    total_price_display.short_description = 'Total'
    total_price_display.admin_order_field = 'total_price'
    
    def order_summary(self, obj):
        """Display order summary with items."""
        if obj.pk:
            items = obj.items.all()
            if items:
                summary = "<ul style='margin: 0; padding-left: 20px;'>"
                for item in items:
                    summary += f"<li>{item.quantity}x {item.product_name} - ${item.subtotal:.2f}</li>"
                summary += "</ul>"
                return format_html(summary)
        return "No items"
    order_summary.short_description = 'Order Items'
    
    # Admin actions
    def mark_as_processing(self, request, queryset):
        """Mark selected orders as processing."""
        updated = queryset.update(status='processing')
        self.message_user(request, f'{updated} orders marked as processing.')
    mark_as_processing.short_description = 'Mark selected orders as processing'
    
    def mark_as_shipped(self, request, queryset):
        """Mark selected orders as shipped."""
        updated = queryset.update(status='shipped')
        self.message_user(request, f'{updated} orders marked as shipped.')
    mark_as_shipped.short_description = 'Mark selected orders as shipped'
    
    def mark_as_delivered(self, request, queryset):
        """Mark selected orders as delivered."""
        updated = queryset.update(status='delivered')
        self.message_user(request, f'{updated} orders marked as delivered.')
    mark_as_delivered.short_description = 'Mark selected orders as delivered'
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected orders as cancelled."""
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} orders marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark selected orders as cancelled'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """
    Admin configuration for OrderItem model.
    """
    list_display = ('order', 'product_name', 'quantity', 'product_price', 'subtotal_display')
    list_filter = ('order__status', 'order__created_at')
    search_fields = ('product_name', 'product_sku', 'order__order_number')
    readonly_fields = ('subtotal_display',)
    ordering = ('-order__created_at',)
    
    def subtotal_display(self, obj):
        return f"${obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'
    subtotal_display.admin_order_field = 'subtotal'


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for OrderStatusHistory model.
    """
    list_display = ('order', 'old_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('old_status', 'new_status', 'created_at')
    search_fields = ('order__order_number', 'changed_by__email', 'notes')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


# Register CartItem separately if needed for individual management
@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Admin configuration for CartItem model.
    """
    list_display = ('cart', 'product', 'quantity', 'subtotal_display', 'added_at')
    list_filter = ('added_at', 'cart__user')
    search_fields = ('product__name', 'cart__user__email')
    readonly_fields = ('subtotal_display', 'added_at')
    ordering = ('-added_at',)
    
    def subtotal_display(self, obj):
        return f"${obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'
    subtotal_display.admin_order_field = 'subtotal' 