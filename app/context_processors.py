from django.conf import settings

from .models import Wishlist, ContactMessage
from .services import CartService


def site_contact_context(request):
    """Site-wide phone and WhatsApp contact for templates."""
    return {
        "site_phone": getattr(settings, "SITE_PHONE", "+91 62384 39926"),
        "site_whatsapp": getattr(settings, "SITE_WHATSAPP", "916238439926"),
    }


def cart_context(request):
    try:
        cart = CartService.get_or_create_cart(request)
        cart_count = sum(item.quantity for item in cart.items.all())
        totals = CartService.compute_totals(cart)
        cart_subtotal = totals.subtotal
    except Exception:
        cart_count = 0
        cart_subtotal = 0
    return {
        "cart_count": cart_count,
        "cart_subtotal": cart_subtotal,
    }


def wishlist_context(request):
    wishlist_count = 0
    wishlist_variant_ids = []
    if getattr(request, "user", None) and request.user.is_authenticated:
        wishlist_variant_ids = list(
            Wishlist.objects.filter(
                user=request.user,
                selected_variant__is_active=True,
                selected_variant__product__is_active=True,
            ).values_list("selected_variant_id", flat=True)
        )
        wishlist_count = len(wishlist_variant_ids)
    return {
        "wishlist_count": wishlist_count,
        "wishlist_variant_ids": wishlist_variant_ids,
        "wishlist_product_ids": [],  # No longer used; kept for template compatibility
    }


def admin_message_badge(request):
    """
    Provide unresolved contact message count for admin navigation badge.
    """
    count = 0
    user = getattr(request, "user", None)
    if user and user.is_authenticated and user.is_staff:
        count = ContactMessage.objects.filter(is_resolved=False).count()
    return {"admin_unresolved_messages": count}

