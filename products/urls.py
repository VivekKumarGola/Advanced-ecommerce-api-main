from django.urls import path
from . import views
from . import cache_views

app_name = 'products'

urlpatterns = [
    # Category endpoints
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/utils/with-counts/', views.categories_with_products_count, name='categories_with_counts'),
    path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    
    # Cache management endpoints (Admin only)
    path('cache/stats/', cache_views.cache_stats, name='cache_stats'),
    path('cache/clear/', cache_views.clear_cache, name='clear_cache'),
    path('cache/flush/', cache_views.flush_all_cache, name='flush_all_cache'),
    path('cache/warm/', cache_views.warm_cache, name='warm_cache'),
    
    # Product search and special endpoints (before slug patterns)
    path('search/', views.ProductSearchView.as_view(), name='product_search'),
    path('featured/', views.FeaturedProductsView.as_view(), name='featured_products'),
    
    # Admin product management endpoints
    path('admin/stock/<int:pk>/', views.ProductStockUpdateView.as_view(), name='product_stock_update'),
    path('admin/bulk-create/', views.ProductBulkCreateView.as_view(), name='product_bulk_create'),
    path('admin/bulk-update-stock/', views.bulk_update_stock, name='bulk_update_stock'),
    path('admin/low-stock/', views.low_stock_products, name='low_stock_products'),
    path('admin/out-of-stock/', views.out_of_stock_products, name='out_of_stock_products'),
    
    # Product endpoints (slug pattern should be last)
    path('', views.ProductListView.as_view(), name='product_list'),
    path('<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
] 