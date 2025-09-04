"""
Django admin configuration for Products app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for Category model.
    """
    list_display = ('name', 'slug', 'description', 'product_count', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'product_count')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Meta Information', {
            'fields': ('created_at', 'updated_at', 'product_count'),
            'classes': ('collapse',)
        }),
    )
    
    def product_count(self, obj):
        """Display the number of products in this category."""
        count = obj.products.count()
        if count > 0:
            url = reverse('admin:products_product_changelist') + f'?category__id__exact={obj.id}'
            return format_html('<a href="{}">{} products</a>', url, count)
        return '0 products'
    product_count.short_description = 'Products'
    product_count.admin_order_field = 'products__count'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Admin configuration for Product model.
    """
    list_display = (
        'name', 'category', 'price', 'stock', 'stock_status', 
        'is_featured', 'is_active', 'product_image', 'created_at'
    )
    list_filter = (
        'category', 'is_featured', 'is_active', 'created_at', 
        'updated_at', 'stock'
    )
    search_fields = ('name', 'description', 'sku')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'stock_status', 'product_image')
    list_editable = ('price', 'stock', 'is_featured', 'is_active')
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'category')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'stock', 'stock_status', 'sku')
        }),
        ('Product Status', {
            'fields': ('is_featured', 'is_active')
        }),
        ('Media', {
            'fields': ('image', 'product_image')
        }),
        ('Meta Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_featured', 'mark_as_not_featured', 'mark_as_active', 'mark_as_inactive']
    
    def stock_status(self, obj):
        """Display stock status with color coding."""
        if obj.stock <= 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">Out of Stock</span>'
            )
        elif obj.stock <= 10:
            return format_html(
                '<span style="color: orange; font-weight: bold;">Low Stock ({} left)</span>',
                obj.stock
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">In Stock ({} left)</span>',
                obj.stock
            )
    stock_status.short_description = 'Stock Status'
    stock_status.admin_order_field = 'stock'
    
    def product_image(self, obj):
        """Display product image thumbnail."""
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    product_image.short_description = 'Image'
    
    # Admin actions
    def mark_as_featured(self, request, queryset):
        """Mark selected products as featured."""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} products marked as featured.')
    mark_as_featured.short_description = 'Mark selected products as featured'
    
    def mark_as_not_featured(self, request, queryset):
        """Unmark selected products as featured."""
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} products unmarked as featured.')
    mark_as_not_featured.short_description = 'Unmark selected products as featured'
    
    def mark_as_active(self, request, queryset):
        """Mark selected products as active."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} products marked as active.')
    mark_as_active.short_description = 'Mark selected products as active'
    
    def mark_as_inactive(self, request, queryset):
        """Mark selected products as inactive."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} products marked as inactive.')
    mark_as_inactive.short_description = 'Mark selected products as inactive'


# Additional admin customizations
admin.site.site_header = "E-commerce Administration"
admin.site.site_title = "E-commerce Admin"
admin.site.index_title = "Welcome to E-commerce Administration" 