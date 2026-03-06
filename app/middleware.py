"""
Middleware: DebugTrace and guest session handling.
"""
from django.conf import settings
from django.db import connection


class EnsureGuestSessionMiddleware:
    """
    For unauthenticated requests, ensure request.session has a session_key
    so guest cart and wishlist (session-based) work reliably.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            if not request.session.session_key:
                request.session.create()
        return self.get_response(request)


class DebugTraceMiddleware:
    """Enable debug cursor for the request when DEBUG_TRACE is True (so connection.queries is populated)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "DEBUG_TRACE", False):
            connection.force_debug_cursor = True
        try:
            return self.get_response(request)
        finally:
            if getattr(settings, "DEBUG_TRACE", False):
                connection.force_debug_cursor = False
