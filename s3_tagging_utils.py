"""
S3 object tagging utilities for AWS billing and cost allocation.

S3 Tagging must be a URL-encoded string: "Key1=Value1&Key2=Value2"
NOT a dict. Values must be safe (no &, =, etc.) and max 256 chars per value.
"""

from urllib.parse import urlencode


def _sanitize_tag_value(value):
    """
    Sanitize a single tag value for S3 compliance.
    Returns None if value should be skipped.
    """
    if value is None:
        return None
    value = str(value).strip()
    if value == "":
        return None
    # Remove/replace unsafe characters per S3 tagging spec
    value = value.replace("&", "_")
    value = value.replace("=", "_")
    value = value.replace("/", "_")
    value = value.replace("#", "")
    # Truncate to 256 chars (S3 limit)
    value = value[:256]
    return value if value else None


def _sanitize_tag_key(key):
    """
    Sanitize tag key (max 128 chars, safe chars only).
    Returns None if key should be skipped.
    """
    if key is None:
        return None
    key = str(key).strip()
    if key == "":
        return None
    key = key.replace("&", "_").replace("=", "_").replace("/", "_")
    key = key[:128]
    return key


def build_safe_tags(tag_dict):
    """
    Build a URL-encoded S3 Tagging string from a dict.

    Args:
        tag_dict: dict like {"product_id": 1, "color": "Red"}

    Returns:
        URL-encoded string like "product_id=1&color=Red"
        or empty string if no valid tags.
    """
    if not tag_dict:
        return ""
    cleaned = {}
    for key, value in tag_dict.items():
        skey = _sanitize_tag_key(key)
        sval = _sanitize_tag_value(value)
        if skey and sval is not None:
            # Strict validation before adding
            assert len(sval) <= 256, "Tag value must be <= 256 chars"
            assert sval != "", "Tag value cannot be empty"
            cleaned[skey] = sval
    return urlencode(cleaned) if cleaned else ""


def validate_tag_value(value):
    """
    Strict validation before upload.
    Raises AssertionError if invalid.
    """
    assert value is not None, "Tag value cannot be None"
    s = str(value).strip()
    assert s != "", "Tag value cannot be empty"
    assert len(s) <= 256, "Tag value must be <= 256 chars"
