from django.conf import settings

from .models import Wishlist, ContactMessage
from .services import CartService
from .delivery_utils import delivery_enabled
from .wishlist_utils import wishlist_enabled


def site_contact_context(request):
    """Site-wide contact details for templates (footer, contact page, WhatsApp FAB, etc.)."""
    return {
        "site_phone": getattr(settings, "SITE_PHONE", "+91 8891923189"),
        "site_whatsapp": getattr(settings, "SITE_WHATSAPP", "918891923189"),
        "site_email": getattr(settings, "SITE_EMAIL", "support.zanhajewels@gmail.com"),
        "site_instagram": getattr(settings, "SITE_INSTAGRAM", "zanhajewels"),
    }


def cart_context(request):
    try:
        cart = CartService.get_or_create_cart(request)
        cart_count = sum(item.quantity for item in cart.items.all())
        totals = CartService.compute_totals(cart)
        cart_subtotal = totals.subtotal
        cart_variant_ids = set()
        cart_simple_product_ids = set()
        for product_id, variant_id in cart.items.values_list("product_id", "selected_variant_id"):
            if variant_id is not None:
                cart_variant_ids.add(variant_id)
            else:
                cart_simple_product_ids.add(product_id)
    except Exception:
        cart_count = 0
        cart_subtotal = 0
        cart_variant_ids = set()
        cart_simple_product_ids = set()
    return {
        "cart_count": cart_count,
        "cart_subtotal": cart_subtotal,
        "cart_variant_ids": cart_variant_ids,
        "cart_simple_product_ids": cart_simple_product_ids,
    }


def wishlist_context(request):
    enabled = wishlist_enabled()
    wishlist_count = 0
    wishlist_variant_ids = []
    user = getattr(request, "user", None)
    if enabled and user and user.is_authenticated:
        wishlist_variant_ids = list(
            Wishlist.objects.filter(
                user=user,
                selected_variant__is_active=True,
                selected_variant__product__is_active=True,
            ).values_list("selected_variant_id", flat=True)
        )
        wishlist_count = len(wishlist_variant_ids)
    return {
        "wishlist_count": wishlist_count,
        "wishlist_variant_ids": wishlist_variant_ids,
        "wishlist_product_ids": [],  # No longer used; kept for template compatibility
        "WISHLIST_ENABLED": enabled,
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


def delivery_settings(request):
    """
    Expose DELIVERY_INTEGRATED to all templates for conditional delivery UI.
    """
    return {
        "DELIVERY_INTEGRATED": delivery_enabled(),
    }


def home_section_flags(request):
    """
    Expose home page / product section feature toggles to templates so that
    sections and admin navigation can be conditionally shown or hidden.
    """
    return {
        "HOME_DEAL_OF_DAY_ENABLED": getattr(settings, "HOME_DEAL_OF_DAY_ENABLED", True),
        "HOME_FEATURED_ENABLED": getattr(settings, "HOME_FEATURED_ENABLED", True),
        "HOME_BESTSELLER_ENABLED": getattr(settings, "HOME_BESTSELLER_ENABLED", True),
        "HOME_RECENTLY_ADDED_ENABLED": getattr(settings, "HOME_RECENTLY_ADDED_ENABLED", True),
        "REVIEW_ENABLED": getattr(settings, "REVIEW_ENABLED", True),
    }


def admin_product_settings(request):
    """Expose admin product flags so add/edit templates can show or hide attributes/variants UI."""
    return {
        "ALLOW_ATTRIBUTES_AND_VARIANTS": getattr(
            settings, "ALLOW_ATTRIBUTES_AND_VARIANTS", True
        ),
    }
