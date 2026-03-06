import json
from django import template
import webcolors
import re

register = template.Library()


@register.filter
def to_json(value):
    """Serialize a list/dict to JSON for use in data attributes. Returns empty array string for invalid values.
    Does NOT use mark_safe so Django will escape quotes when rendered in HTML attributes,
    ensuring valid attribute values that decode correctly via getAttribute()."""
    if value is None:
        return "[]"
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return "[]"


@register.filter
def image_urls_json(queryset_or_list):
    """For ColorVariantImage (or similar) iterable: return JSON array of image URLs for data-card-images."""
    if not queryset_or_list:
        return "[]"
    try:
        urls = []
        for item in queryset_or_list:
            if hasattr(item, "image") and getattr(item.image, "url", None):
                urls.append(item.image.url)
            elif hasattr(item, "url"):
                urls.append(item.url)
        return json.dumps(urls)
    except (TypeError, ValueError):
        return "[]"

# Extended custom color names not found in webcolors library
EXTENDED_COLORS = {
    'olive green': '#6B8E23',
    'dark olive green': '#556B2F',
    'light olive green': '#A4D65E',
    'navy green': '#35530a',
    'forest': '#228B22',
    'light forest': '#32CD32',
}

@register.filter
def color_to_hex(color_name):
    """
    Convert a color name to its hex equivalent using webcolors library.
    Supports all standard CSS color names, extended custom colors, and hex codes.
    Handles both space-separated (e.g., 'dark blue') and hyphenated names.
    If the color name is not found, returns white color (#FFFFFF).
    """
    if not color_name:
        return "#FFFFFF"  # Default white for empty values
    
    color_str = str(color_name).strip()
    
    # If it's already a hex color, validate and return it
    if color_str.startswith('#'):
        if re.match(r'^#[0-9A-Fa-f]{6}$', color_str) or re.match(r'^#[0-9A-Fa-f]{3}$', color_str):
            return color_str
    
    # Convert to lowercase
    color_lower = color_str.lower()
    
    # Check extended colors first
    if color_lower in EXTENDED_COLORS:
        return EXTENDED_COLORS[color_lower]
    
    # Try different formats for webcolors
    # 1. Try as-is first
    try:
        hex_code = webcolors.name_to_hex(color_lower)
        return hex_code
    except ValueError:
        pass
    
    # 2. Try removing spaces (e.g., 'dark blue' -> 'darkblue')
    color_no_spaces = color_lower.replace(' ', '')
    try:
        hex_code = webcolors.name_to_hex(color_no_spaces)
        return hex_code
    except ValueError:
        pass
    
    # 3. Try replacing spaces with underscores
    color_underscored = color_lower.replace(' ', '_')
    try:
        hex_code = webcolors.name_to_hex(color_underscored)
        return hex_code
    except ValueError:
        pass
    
    # Color name not found, return default white
    return "#FFFFFF"
