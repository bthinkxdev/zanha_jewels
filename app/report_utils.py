"""
Report utilities: date ranges, filter application, summary aggregation.
Cache-key helpers are Redis-ready (use with django.core.cache).
Handles nulls and missing relations safely.
"""
from datetime import datetime, timedelta, time as dt_time
from decimal import Decimal
from django.db.models import (
    Count,
    Sum,
    F,
    Value,
    CharField,
)
from django.utils import timezone
from django.conf import settings

from .models import Order, OrderItem, Product, Category, Payment, Variant


# ---------------------------------------------------------------------------
# Date range presets
# ---------------------------------------------------------------------------

DATE_PRESETS = [
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("this_week", "This Week"),
    ("this_month", "This Month"),
    ("custom", "Custom"),
]


def get_date_range(preset, date_from=None, date_to=None):
    """
    Return (start_datetime, end_datetime) in active timezone.
    end_datetime is end of day for the end date.
    """
    tz = timezone.get_current_timezone()
    now = timezone.now()
    today = now.date()

    if preset == "today":
        start = timezone.make_aware(datetime.combine(today, dt_time.min), tz)
        end = now
        return start, end
    if preset == "yesterday":
        yesterday = today - timedelta(days=1)
        start = timezone.make_aware(datetime.combine(yesterday, dt_time.min), tz)
        end = timezone.make_aware(datetime.combine(yesterday, dt_time.max), tz)
        return start, end
    if preset == "this_week":
        # ISO week: Monday = start
        start_week = today - timedelta(days=today.weekday())
        start = timezone.make_aware(datetime.combine(start_week, dt_time.min), tz)
        end = now
        return start, end
    if preset == "this_month":
        start_month = today.replace(day=1)
        start = timezone.make_aware(datetime.combine(start_month, dt_time.min), tz)
        end = now
        return start, end
    if preset == "custom" and date_from and date_to:
        from django.utils.dateparse import parse_date

        d_from = parse_date(date_from) if isinstance(date_from, str) else date_from
        d_to = parse_date(date_to) if isinstance(date_to, str) else date_to
        if d_from and d_to:
            start = timezone.make_aware(datetime.combine(d_from, dt_time.min), tz)
            end = timezone.make_aware(datetime.combine(d_to, dt_time.max), tz)
            if start <= end:
                return start, end
    return None, None


# ---------------------------------------------------------------------------
# Base order queryset with filters (safe for null user, missing payment)
# ---------------------------------------------------------------------------

def get_base_order_queryset():
    """Orders with address, user, and payment. Optimized to avoid N+1."""
    return Order.objects.select_related("address", "user", "payment").prefetch_related(
        "items__product",
        "items__selected_variant",
    )


def apply_report_filters(
    qs,
    *,
    date_from=None,
    date_to=None,
    date_preset="this_month",
    order_status=None,
    payment_method=None,
    product_id=None,
    category_id=None,
    user_id=None,
    guest_only=False,
    min_amount=None,
    max_amount=None,
):
    """
    Apply common report filters to an Order queryset.
    All filters are optional. Handles nulls safely.
    """
    start, end = get_date_range(date_preset or "this_month", date_from, date_to)
    if start is not None and end is not None:
        qs = qs.filter(created_at__gte=start, created_at__lte=end)

    if order_status:
        qs = qs.filter(status=order_status)
    if payment_method:
        qs = qs.filter(payment__method=payment_method)
    if product_id:
        qs = qs.filter(items__product_id=product_id).distinct()
    if category_id:
        qs = qs.filter(items__product__category_id=category_id).distinct()
    if user_id:
        qs = qs.filter(user_id=user_id)
    if guest_only:
        qs = qs.filter(user__isnull=True)
    if min_amount is not None:
        try:
            min_amount = Decimal(str(min_amount))
            qs = qs.filter(total__gte=min_amount)
        except Exception:
            pass
    if max_amount is not None:
        try:
            max_amount = Decimal(str(max_amount))
            qs = qs.filter(total__lte=max_amount)
        except Exception:
            pass
    return qs


# Keys that apply_report_filters() accepts (views may pass sort, page, page_size etc.)
_ORDER_FILTER_KEYS = {
    "date_from", "date_to", "date_preset", "order_status", "payment_method",
    "product_id", "category_id", "user_id", "guest_only", "min_amount", "max_amount",
}


def _filter_kwargs_for_report(filters):
    """Return only kwargs valid for apply_report_filters."""
    return {k: v for k, v in filters.items() if k in _ORDER_FILTER_KEYS}


def get_report_summary(qs, cache_key=None):
    """
    Compute summary for report: total_orders, total_revenue, avg_order_value, top_product.
    Uses single aggregated query where possible. Safe for empty qs.
    """
    cache = getattr(settings, "CACHES", {}) and getattr(settings, "CACHE_REPORT_SUMMARY", True)
    if cache and cache_key:
        from django.core.cache import cache as cache_backend
        data = cache_backend.get(cache_key)
        if data is not None:
            return data

    agg = qs.aggregate(
        total_orders=Count("id", distinct=True),
        total_revenue=Sum("total"),
    )
    total_orders = agg["total_orders"] or 0
    total_revenue = agg["total_revenue"] or Decimal("0")
    avg_order_value = (total_revenue / total_orders) if total_orders else Decimal("0")

    # Top-selling product in this filtered set (by quantity sold)
    top_row = (
        OrderItem.objects.filter(order__in=qs)
        .values("product_id", "product_name")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")
        .first()
    )
    top_product_name = None
    if top_row:
        top_product_name = top_row.get("product_name") or ""
        if not top_product_name and top_row.get("product_id"):
            try:
                p = Product.objects.filter(pk=top_row["product_id"]).values_list("name", flat=True).first()
                top_product_name = p or "Unknown"
            except Exception:
                top_product_name = "Unknown"

    result = {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "avg_order_value": avg_order_value,
        "top_product_name": top_product_name or "—",
    }
    if cache and cache_key:
        from django.core.cache import cache as cache_backend
        cache_backend.set(cache_key, result, timeout=300)  # 5 min
    return result


def report_cache_key(prefix, **params):
    """Build a cache key for report summary (Redis-ready string)."""
    parts = [str(k) + "=" + str(v) for k, v in sorted(params.items()) if v is not None and v != ""]
    return f"report:{prefix}:{':'.join(parts)}" if parts else f"report:{prefix}:all"


# ---------------------------------------------------------------------------
# Report-specific querysets (optimized, no N+1)
# ---------------------------------------------------------------------------

def get_orders_report_queryset(filters):
    """Orders report: list of orders with applied filters."""
    qs = get_base_order_queryset()
    qs = apply_report_filters(qs, **_filter_kwargs_for_report(filters))
    return qs.order_by("-created_at")


def get_sales_report_queryset(filters):
    """Sales report: same as orders but focused on revenue; can reuse orders queryset."""
    return get_orders_report_queryset(filters)


def get_product_performance_queryset(filters):
    """
    Product performance: products with sold qty and revenue in date range.
    Uses OrderItem aggregated by product. Respects order filters (date, status, payment, etc.).
    """
    order_qs = get_base_order_queryset()
    order_qs = apply_report_filters(order_qs, **_filter_kwargs_for_report(filters))

    return (
        Product.objects.filter(order_items__order__in=order_qs)
        .annotate(
            units_sold=Sum("order_items__quantity"),
            revenue=Sum(F("order_items__quantity") * F("order_items__unit_price")),
            order_count=Count("order_items__order", distinct=True),
        )
        .filter(units_sold__gt=0)
        .order_by("-units_sold")
        .select_related("category")
        .distinct()
    )


def get_customer_report_queryset(filters):
    """
    Customer report: users (and optionally guests) with order count and total spent.
    Uses Order aggregated by user. For guests we use a placeholder or address email.
    """
    order_qs = get_base_order_queryset()
    order_qs = apply_report_filters(order_qs, **_filter_kwargs_for_report(filters))

    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Registered users: annotate orders and revenue
    users_qs = (
        User.objects.filter(orders__in=order_qs)
        .annotate(
            order_count=Count("orders", distinct=True),
            total_spent=Sum("orders__total"),
        )
        .distinct()
        .order_by("-total_spent")
    )
    return users_qs


def get_inventory_report_queryset(filters):
    """
    Inventory/stock report: Variant with product and category.
    Optional filter by product_id / category_id from filters.
    """
    qs = (
        Variant.objects.select_related("product", "product__category")
        .filter(product__is_active=True)
    )
    if filters.get("product_id"):
        qs = qs.filter(product_id=filters["product_id"])
    if filters.get("category_id"):
        qs = qs.filter(product__category_id=filters["category_id"])
    return qs.order_by("product__name", "display_order", "id")
