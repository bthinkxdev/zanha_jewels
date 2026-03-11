from django.conf import settings


def wishlist_enabled() -> bool:
    """
    Central helper to check if wishlist feature is enabled.
    Defaults to True when the setting is missing.
    """
    return getattr(settings, "WISHLIST_ENABLED", True)

