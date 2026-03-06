from decimal import Decimal

from ..models import Order


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def calculate_parcel(order: Order) -> dict:
    """
    Calculate balanced parcel dimensions and weight for a given order.

    Uses stacked height logic + volumetric weight:
      - total_weight = sum(variant.weight * qty)
      - length  = max(variant.length)
      - breadth = max(variant.breadth)
      - height  = sum(variant.height * qty)
      - volumetric_weight = (length * breadth * height) / 5000
      - final_weight = max(total_weight, volumetric_weight)

    All dimensions are in cm and weight in kg.
    """
    total_weight = Decimal("0")
    lengths = []
    breadths = []
    heights = []

    items = order.items.select_related("selected_variant").all()

    for item in items:
        variant = item.selected_variant
        if not variant:
            continue
        qty = Decimal(item.quantity or 0)

        weight = _to_decimal(getattr(variant, "weight", 0))
        length = _to_decimal(getattr(variant, "length", 0))
        breadth = _to_decimal(getattr(variant, "breadth", 0))
        height = _to_decimal(getattr(variant, "height", 0))

        total_weight += weight * qty
        if length > 0:
            lengths.append(length)
        if breadth > 0:
            breadths.append(breadth)
        if height > 0:
            heights.append(height * qty)

    if lengths:
        length = max(lengths)
    else:
        length = Decimal("0")
    if breadths:
        breadth = max(breadths)
    else:
        breadth = Decimal("0")
    if heights:
        height = sum(heights)
    else:
        height = Decimal("0")

    volumetric_weight = Decimal("0")
    if length > 0 and breadth > 0 and height > 0:
        volumetric_weight = (length * breadth * height) / Decimal("5000")

    final_weight = max(total_weight, volumetric_weight)

    return {
        "length": round(length, 2),
        "breadth": round(breadth, 2),
        "height": round(height, 2),
        "weight": round(final_weight, 2),
    }

