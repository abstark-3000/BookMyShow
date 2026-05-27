from django.urls import path
from . import views
urlpatterns=[
    path('',views.movie_list,name='movie_list'),
    path(
        '<int:movie_id>/theaters/',
        views.theater_list,
        name='theater_list'
    ),
    path('theater/<int:theater_id>/seats/book/',views.book_seats,name='book_seats'),
    path('<int:movie_id>/', views.movie_detail, name='movie_detail'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/webhook/', views.razorpay_webhook, name='razorpay_webhook'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('payment/test-success/<str:order_id>/', views.test_payment_success, name='test_payment_success'),
]