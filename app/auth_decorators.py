"""
Custom authentication decorators and mixins for OTP-based authentication
"""

from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse


def login_required_for_action(view_func):
    """
    Decorator that redirects to OTP login if user is not authenticated
    Preserves the current URL as 'next' parameter
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Get the current URL to redirect back after login
            next_url = request.get_full_path()
            login_url = f"{reverse('auth:login')}?next={next_url}"
            return redirect(login_url)
        return view_func(request, *args, **kwargs)
    return wrapper


class LoginRequiredForActionMixin:
    """
    Mixin that redirects to OTP login if user is not authenticated
    Use this for class-based views that require authentication
    """
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Get the current URL to redirect back after login
            next_url = request.get_full_path()
            login_url = f"{reverse('auth:login')}?next={next_url}"
            return redirect(login_url)
        return super().dispatch(request, *args, **kwargs)

