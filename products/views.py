from django.shortcuts import render
from django.db import models

from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.db.models import Q, Count, Prefetch
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Category, Product, ProductImage
from .serializers import (
    CategoryListSerializer,
    CategoryDetailSerializer,
    CategoryCreateUpdateSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    ProductStockUpdateSerializer,
    ProductBulkCreateSerializer,
    ProductSearchSerializer,
    ProductImageSerializer,
)
from .permissions import IsAdminOrReadOnly, IsAdminUser, CanManageProducts
from .filters import ProductFilter
from utils.cache import CacheManager, CacheKeys, cache_result


# ============================================================================
# CATEGORY VIEWS
# ============================================================================

class CategoryListView(generics.ListCreateAPIView):
    """
    List all categories or create a new category
    """
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Optimized queryset with product counts"""
        return Category.objects.filter(is_active=True).annotate(
            products_count=Count('products', filter=Q(products__is_active=True))
        ).select_related().order_by('name')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CategoryCreateUpdateSerializer
        return CategoryListSerializer
    
    @swagger_auto_schema(
        operation_description="Get list of all categories",
        responses={200: CategoryListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        # Generate cache key based on search/ordering params
        search = request.query_params.get('search', '')
        ordering = request.query_params.get('ordering', 'name')
        cache_key = CacheKeys.category_list() + f"_search_{search}_order_{ordering}"
        
        # Try to get cached data
        cached_data = CacheManager.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        response = super().get(request, *args, **kwargs)
        
        # Cache the response for 1 hour
        if response.status_code == 200:
            CacheManager.set(cache_key, response.data, 'long')
        
        return response
    
    @swagger_auto_schema(
        operation_description="Create a new category (Admin only)",
        request_body=CategoryCreateUpdateSerializer,
        responses={
            201: CategoryDetailSerializer,
            400: 'Bad Request',
            403: 'Forbidden'
        }
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # Invalidate cache on creation
        if response.status_code == 201:
            CacheManager.invalidate_group('category')
            CacheManager.invalidate_group('product')  # Products may reference categories
        
        return response


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a category
    """
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Optimized queryset"""
        return Category.objects.select_related().prefetch_related(
            Prefetch('products', queryset=Product.objects.filter(is_active=True))
        )
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CategoryCreateUpdateSerializer
        return CategoryDetailSerializer
    
    @swagger_auto_schema(
        operation_description="Get category details",
        responses={200: CategoryDetailSerializer}
    )
    def get(self, request, *args, **kwargs):
        # Generate cache key for this specific category
        slug = kwargs.get('slug')
        cache_key = CacheManager.generate_key('category', 'detail', slug)
        
        # Try to get from cache
        cached_data = CacheManager.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        response = super().get(request, *args, **kwargs)
        
        # Cache successful response
        if response.status_code == 200:
            CacheManager.set(cache_key, response.data, 'long')
        
        return response
    
    @swagger_auto_schema(
        operation_description="Update category (Admin only)",
        request_body=CategoryCreateUpdateSerializer,
        responses={
            200: CategoryDetailSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        
        # Invalidate cache on update
        if response.status_code == 200:
            CacheManager.invalidate_group('category')
            CacheManager.invalidate_group('product')
        
        return response
    
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        
        # Invalidate cache on deletion
        if response.status_code == 204:
            CacheManager.invalidate_group('category')
            CacheManager.invalidate_group('product')
        
        return response
    
    @swagger_auto_schema(
        operation_description="Delete category (Admin only)",
        responses={
            204: 'Category deleted successfully',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        
        # Invalidate cache on deletion
        if response.status_code == 204:
            cache.delete('categories_list')
        
        return response


# ============================================================================
# PRODUCT VIEWS
# ============================================================================

class ProductListView(generics.ListCreateAPIView):
    """
    List all products or create a new product
    """
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['name', 'price', 'stock', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Optimized queryset with select_related"""
        return Product.objects.filter(is_active=True).select_related(
            'category'
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductCreateUpdateSerializer
        return ProductListSerializer
    
    @swagger_auto_schema(
        operation_description="Get list of all products with filtering and pagination",
        manual_parameters=[
            openapi.Parameter('category', openapi.IN_QUERY, description="Filter by category ID", type=openapi.TYPE_INTEGER),
            openapi.Parameter('min_price', openapi.IN_QUERY, description="Minimum price filter", type=openapi.TYPE_NUMBER),
            openapi.Parameter('max_price', openapi.IN_QUERY, description="Maximum price filter", type=openapi.TYPE_NUMBER),
            openapi.Parameter('in_stock', openapi.IN_QUERY, description="Filter products in stock", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('is_featured', openapi.IN_QUERY, description="Filter featured products", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('search', openapi.IN_QUERY, description="Search in name, description, SKU", type=openapi.TYPE_STRING),
            openapi.Parameter('ordering', openapi.IN_QUERY, description="Order by field", type=openapi.TYPE_STRING),
        ],
        responses={200: ProductListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        # Generate cache key based on query parameters
        page = request.query_params.get('page', 1)
        category = request.query_params.get('category')
        search = request.query_params.get('search', '')
        filters = {k: v for k, v in request.query_params.items() 
                  if k not in ['page', 'category', 'search']}
        
        cache_key = CacheKeys.product_list(
            page=page, 
            category=category, 
            search=search, 
            **filters
        )
        
        # Try to get from cache
        cached_data = CacheManager.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        response = super().get(request, *args, **kwargs)
        
        # Cache successful response for 30 minutes
        if response.status_code == 200:
            CacheManager.set(cache_key, response.data, 'medium')
        
        return response
    
    @swagger_auto_schema(
        operation_description="Create a new product (Admin only)",
        request_body=ProductCreateUpdateSerializer,
        responses={
            201: ProductDetailSerializer,
            400: 'Bad Request',
            403: 'Forbidden'
        }
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # Return detailed view of created product and invalidate cache
        if response.status_code == 201:
            # Invalidate product and related caches
            CacheManager.invalidate_group('product')
            CacheManager.invalidate_group('category')  # Category counts may change
            CacheManager.invalidate_group('search')    # Search results may change
            
            product = Product.objects.get(id=response.data['id'])
            serializer = ProductDetailSerializer(product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return response


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a product
    """
    queryset = Product.objects.all().select_related('category').prefetch_related('additional_images')
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer
    
    @swagger_auto_schema(
        operation_description="Get product details",
        responses={200: ProductDetailSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Update product (Admin only)",
        request_body=ProductCreateUpdateSerializer,
        responses={
            200: ProductDetailSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Delete product (Admin only)",
        responses={
            204: 'Product deleted successfully',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class ProductStockUpdateView(generics.UpdateAPIView):
    """
    Update product stock only
    """
    queryset = Product.objects.all()
    serializer_class = ProductStockUpdateSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'pk'
    
    @swagger_auto_schema(
        operation_description="Update product stock (Admin only)",
        request_body=ProductStockUpdateSerializer,
        responses={
            200: ProductStockUpdateSerializer,
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class ProductBulkCreateView(generics.CreateAPIView):
    """
    Bulk create products
    """
    serializer_class = ProductBulkCreateSerializer
    permission_classes = [IsAdminUser]
    
    @swagger_auto_schema(
        operation_description="Bulk create products (Admin only)",
        request_body=ProductBulkCreateSerializer,
        responses={
            201: 'Products created successfully',
            400: 'Bad Request',
            403: 'Forbidden'
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class FeaturedProductsView(generics.ListAPIView):
    """
    List featured products
    """
    serializer_class = ProductListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Product.objects.filter(
            is_active=True, 
            is_featured=True
        ).select_related('category').order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get list of featured products",
        responses={200: ProductListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        # Try to get cached data
        cache_key = 'featured_products'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return Response(cached_data)
        
        response = super().get(request, *args, **kwargs)
        
        # Cache the response for 30 minutes
        if response.status_code == 200:
            cache.set(cache_key, response.data, 1800)  # 30 minutes
        
        return response


class ProductSearchView(APIView):
    """
    Advanced product search with filters
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Advanced product search",
        query_serializer=ProductSearchSerializer,
        responses={200: ProductListSerializer(many=True)}
    )
    def get(self, request):
        serializer = ProductSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        filters = serializer.validated_data
        queryset = Product.objects.filter(is_active=True).select_related('category')
        
        # Apply search filters
        if filters.get('query'):
            query = filters['query']
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(sku__icontains=query)
            )
        
        if filters.get('category'):
            queryset = queryset.filter(category_id=filters['category'])
        
        if filters.get('min_price'):
            queryset = queryset.filter(price__gte=filters['min_price'])
        
        if filters.get('max_price'):
            queryset = queryset.filter(price__lte=filters['max_price'])
        
        if filters.get('in_stock') is not None:
            if filters['in_stock']:
                queryset = queryset.filter(stock__gt=0)
            else:
                queryset = queryset.filter(stock=0)
        
        if filters.get('is_featured') is not None:
            queryset = queryset.filter(is_featured=filters['is_featured'])
        
        # Apply ordering
        if filters.get('ordering'):
            queryset = queryset.order_by(filters['ordering'])
        else:
            queryset = queryset.order_by('-created_at')
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @property
    def paginator(self):
        """Get the paginator instance"""
        if not hasattr(self, '_paginator'):
            from rest_framework.pagination import PageNumberPagination
            self._paginator = PageNumberPagination()
            self._paginator.page_size = 10
        return self._paginator
    
    def paginate_queryset(self, queryset):
        """Paginate the queryset"""
        return self.paginator.paginate_queryset(queryset, self.request, view=self)
    
    def get_paginated_response(self, data):
        """Return paginated response"""
        return self.paginator.get_paginated_response(data)


# ============================================================================
# UTILITY VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def categories_with_products_count(request):
    """
    Get all categories with their product counts
    """
    cache_key = 'categories_with_counts'
    cached_data = cache.get(cache_key)
    
    if cached_data is not None:
        return Response(cached_data)
    
    categories = Category.objects.filter(is_active=True).order_by('name')
    serializer = CategoryListSerializer(categories, many=True)
    
    # Cache for 1 hour
    cache.set(cache_key, serializer.data, settings.CACHE_TTL)
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def low_stock_products(request):
    """
    Get products with low stock (Admin only)
    """
    low_stock_products = Product.objects.filter(
        is_active=True,
        stock__lte=models.F('low_stock_threshold'),
        stock__gt=0
    ).select_related('category').order_by('stock')
    
    serializer = ProductListSerializer(low_stock_products, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def out_of_stock_products(request):
    """
    Get out of stock products (Admin only)
    """
    out_of_stock = Product.objects.filter(
        is_active=True,
        stock=0
    ).select_related('category').order_by('-updated_at')
    
    serializer = ProductListSerializer(out_of_stock, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_update_stock(request):
    """
    Bulk update product stock (Admin only)
    """
    updates = request.data.get('updates', [])
    
    if not updates:
        return Response(
            {'error': 'No updates provided'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    updated_products = []
    errors = []
    
    for update in updates:
        try:
            product_id = update.get('id')
            new_stock = update.get('stock')
            
            if product_id is None or new_stock is None:
                errors.append(f"Missing id or stock in update: {update}")
                continue
            
            product = Product.objects.get(id=product_id)
            product.stock = new_stock
            product.save(update_fields=['stock', 'updated_at'])
            updated_products.append(product.id)
            
        except Product.DoesNotExist:
            errors.append(f"Product with id {product_id} not found")
        except Exception as e:
            errors.append(f"Error updating product {product_id}: {str(e)}")
    
    # Invalidate cache
    cache.delete_many(['products_list', 'featured_products'])
    
    return Response({
        'updated_products': updated_products,
        'errors': errors,
        'total_updated': len(updated_products)
    })
