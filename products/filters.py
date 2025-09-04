import django_filters
from django.db import models
from .models import Product, Category


class ProductFilter(django_filters.FilterSet):
    """
    FilterSet for Product model with comprehensive filtering options
    """
    
    # Price range filters
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    
    # Category filter
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.filter(is_active=True),
        field_name='category'
    )
    category_name = django_filters.CharFilter(
        field_name='category__name',
        lookup_expr='icontains'
    )
    
    # Stock filters
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')
    low_stock = django_filters.BooleanFilter(method='filter_low_stock')
    
    # Status filters
    is_active = django_filters.BooleanFilter(field_name='is_active')
    is_featured = django_filters.BooleanFilter(field_name='is_featured')
    
    # Text search
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    sku = django_filters.CharFilter(field_name='sku', lookup_expr='icontains')
    
    # Date filters
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    
    # Stock range filters
    min_stock = django_filters.NumberFilter(field_name='stock', lookup_expr='gte')
    max_stock = django_filters.NumberFilter(field_name='stock', lookup_expr='lte')
    
    class Meta:
        model = Product
        fields = {
            'price': ['exact', 'gte', 'lte'],
            'stock': ['exact', 'gte', 'lte'],
            'is_active': ['exact'],
            'is_featured': ['exact'],
            'category': ['exact'],
        }
    
    def filter_in_stock(self, queryset, name, value):
        """Filter products that are in stock"""
        if value:
            return queryset.filter(stock__gt=0)
        else:
            return queryset.filter(stock=0)
    
    def filter_low_stock(self, queryset, name, value):
        """Filter products with low stock"""
        if value:
            return queryset.filter(
                stock__gt=0,
                stock__lte=models.F('low_stock_threshold')
            )
        return queryset


class CategoryFilter(django_filters.FilterSet):
    """
    FilterSet for Category model
    """
    
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    
    class Meta:
        model = Category
        fields = {
            'name': ['icontains'],
            'is_active': ['exact'],
        } 