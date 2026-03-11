from django.conf import settings


def delivery_enabled() -> bool:
    """
    Central helper to check if delivery/shipping integration is enabled.
    Falls back to False when the setting is missing.
    """
    return getattr(settings, "DELIVERY_INTEGRATED", False)

