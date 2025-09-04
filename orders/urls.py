from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Cart endpoints
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.AddToCartView.as_view(), name='add_to_cart'),
    path('cart/clear/', views.ClearCartView.as_view(), name='clear_cart'),
    path('cart/items/<int:item_id>/', views.CartItemView.as_view(), name='cart_item'),
    
    # Order endpoints
    path('', views.OrderListView.as_view(), name='order_list'),
    path('create/', views.CreateOrderView.as_view(), name='create_order'),
    path('<str:order_number>/', views.OrderDetailView.as_view(), name='order_detail'),
    
    # User utility endpoints
    path('user/summary/', views.user_order_summary, name='user_order_summary'),
    
    # Admin order management
    path('admin/', views.AdminOrderListView.as_view(), name='admin_order_list'),
    path('admin/<str:order_number>/', views.AdminOrderDetailView.as_view(), name='admin_order_detail'),
    path('admin/<str:order_number>/status/', views.UpdateOrderStatusView.as_view(), name='update_order_status'),
    path('admin/<str:order_number>/payment/', views.UpdatePaymentStatusView.as_view(), name='update_payment_status'),
    
    # Admin utility endpoints
    path('admin/statistics/', views.order_statistics, name='order_statistics'),
    path('admin/recent/', views.recent_orders, name='recent_orders'),
    path('admin/pending/', views.pending_orders, name='pending_orders'),
    path('admin/bulk-update-status/', views.bulk_update_order_status, name='bulk_update_order_status'),
] 