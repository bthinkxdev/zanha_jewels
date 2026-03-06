"""
URL patterns for authentication
"""

from django.urls import path
from . import auth_views

app_name = 'auth'

urlpatterns = [
    # OTP Login
    path('login/', auth_views.OTPLoginView.as_view(), name='login'),
    path('login/ajax/', auth_views.OTPLoginAjaxView.as_view(), name='login_ajax'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Account Management
    path('account/', auth_views.AccountDashboardView.as_view(), name='account'),
    path('account/profile/', auth_views.ProfileView.as_view(), name='profile'),
    
    # Address Management
    path('account/addresses/', auth_views.AddressListView.as_view(), name='address_list'),
    path('account/addresses/add/', auth_views.AddressCreateView.as_view(), name='address_create'),
    path('account/addresses/<int:pk>/edit/', auth_views.AddressUpdateView.as_view(), name='address_edit'),
    path('account/addresses/<int:pk>/delete/', auth_views.AddressDeleteView.as_view(), name='address_delete'),
]

