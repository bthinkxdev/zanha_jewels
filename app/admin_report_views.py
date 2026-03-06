"""
Admin report views: Orders, Sales, Product Performance, Customer, Inventory.
AJAX filtering, pagination, sorting, CSV/Excel export.
Admin-only; null-safe; optimized queries.
"""
import csv
from decimal import Decimal
from io import BytesIO
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import TemplateView, View
from django.core.paginator import Paginator

from .models import Order, OrderItem, Payment, Product, Category
from .admin_views import StaffRequiredMixin
from .report_utils import (
    DATE_PRESETS,
    get_date_range,
    get_base_order_queryset,
    apply_report_filters,
    get_report_summary,
    report_cache_key,
    get_orders_report_queryset,
    get_product_performance_queryset,
    get_customer_report_queryset,
    get_inventory_report_queryset,
    _filter_kwargs_for_report,
)


def _get_report_filters(request):
    """Parse request GET into filter dict for report_utils."""
    get = request.GET
    return {
        "date_preset": get.get("date_preset") or "this_month",
        "date_from": get.get("date_from"),
        "date_to": get.get("date_to"),
        "order_status": get.get("status"),
        "payment_method": get.get("payment_method"),
        "product_id": get.get("product") or get.get("product_id"),
        "category_id": get.get("category") or get.get("category_id"),
        "user_id": get.get("user") or get.get("user_id"),
        "guest_only": get.get("guest_only") == "1" or get.get("guest_only") == "true",
        "min_amount": get.get("min_amount"),
        "max_amount": get.get("max_amount"),
        "sort": get.get("sort") or "-created_at",
        "page": get.get("page", 1),
        "page_size": min(int(get.get("page_size") or 20), 100),
    }


def _apply_sort_orders(qs, sort_param):
    """Apply sorting to Order queryset. Safe allowed fields only."""
    allowed = {"created_at", "-created_at", "total", "-total", "order_number", "-order_number", "status"}
    if sort_param in allowed:
        return qs.order_by(sort_param)
    return qs.order_by("-created_at")


def _apply_sort_products(qs, sort_param):
    allowed = {"units_sold", "-units_sold", "revenue", "-revenue", "name", "-name", "order_count", "-order_count"}
    if sort_param in allowed:
        return qs.order_by(sort_param)
    return qs.order_by("-units_sold")


def _apply_sort_customers(qs, sort_param):
    allowed = {"order_count", "-order_count", "total_spent", "-total_spent", "username", "-username", "email", "-email"}
    if sort_param in allowed:
        return qs.order_by(sort_param)
    return qs.order_by("-total_spent")


# ---------------------------------------------------------------------------
# Reports hub
# ---------------------------------------------------------------------------

class ReportsDashboardView(StaffRequiredMixin, TemplateView):
    template_name = "admin/reports/report_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "reports"
        # Lock down reports list in UI:
        # only expose the Sales report tile in the reports hub.
        context["report_types"] = [
            {"key": "sales", "name": "Sales Report", "url": "admin_panel:report_sales", "icon": "fa-chart-line"},
        ]
        return context


# ---------------------------------------------------------------------------
# Orders Report
# ---------------------------------------------------------------------------

class OrdersReportView(StaffRequiredMixin, TemplateView):
    template_name = "admin/reports/report_orders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = _get_report_filters(self.request)
        qs = get_orders_report_queryset(filters)
        qs = _apply_sort_orders(qs, filters["sort"])

        from django.conf import settings as django_settings
        _f = _get_report_filters(self.request)
        _cache_params = {k: _f[k] for k in _f if k not in ("sort", "page", "page_size")}
        cache_key = report_cache_key("orders", **_cache_params) if getattr(django_settings, "CACHE_REPORT_SUMMARY", False) else None
        summary = get_report_summary(qs, cache_key=cache_key)

        paginator = Paginator(qs, filters["page_size"])
        page = paginator.get_page(filters["page"])

        context.update({
            "active_menu": "reports",
            "report_type": "orders",
            "summary": summary,
            "page_obj": page,
            "orders": page.object_list,
            "date_presets": DATE_PRESETS,
            "filters": filters,
            "status_choices": Order.Status.choices,
            "payment_choices": Payment.Method.choices,
            "products": Product.objects.filter(is_active=True).order_by("name")[:200],
            "categories": Category.objects.filter(is_active=True).order_by("name"),
            "sort": filters["sort"],
        })
        return context


# ---------------------------------------------------------------------------
# Sales Report (same data as orders, different emphasis / columns if needed)
# ---------------------------------------------------------------------------

class SalesReportView(StaffRequiredMixin, TemplateView):
    template_name = "admin/reports/report_sales.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = _get_report_filters(self.request)
        qs = get_orders_report_queryset(filters)
        qs = _apply_sort_orders(qs, filters["sort"])

        from django.conf import settings as django_settings
        _f = _get_report_filters(self.request)
        _cache_params = {k: _f[k] for k in _f if k not in ("sort", "page", "page_size")}
        cache_key = report_cache_key("sales", **_cache_params) if getattr(django_settings, "CACHE_REPORT_SUMMARY", False) else None
        summary = get_report_summary(qs, cache_key=cache_key)

        paginator = Paginator(qs, filters["page_size"])
        page = paginator.get_page(filters["page"])

        context.update({
            "active_menu": "reports",
            "report_type": "sales",
            "summary": summary,
            "page_obj": page,
            "orders": page.object_list,
            "date_presets": DATE_PRESETS,
            "filters": filters,
            "status_choices": Order.Status.choices,
            "payment_choices": Payment.Method.choices,
            "products": Product.objects.filter(is_active=True).order_by("name")[:200],
            "categories": Category.objects.filter(is_active=True).order_by("name"),
            "sort": filters["sort"],
        })
        return context


# ---------------------------------------------------------------------------
# Product Performance Report
# ---------------------------------------------------------------------------

class ProductPerformanceReportView(StaffRequiredMixin, TemplateView):
    template_name = "admin/reports/report_products.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = _get_report_filters(self.request)
        qs = get_product_performance_queryset(filters)
        qs = _apply_sort_products(qs, filters["sort"])

        # Summary for product report: use same order-based summary
        order_qs = get_base_order_queryset()
        order_qs = apply_report_filters(order_qs, **_filter_kwargs_for_report(filters))
        from django.conf import settings as django_settings
        _f = _get_report_filters(self.request)
        _cache_params = {k: _f[k] for k in _f if k not in ("sort", "page", "page_size")}
        cache_key = report_cache_key("products", **_cache_params) if getattr(django_settings, "CACHE_REPORT_SUMMARY", False) else None
        summary = get_report_summary(order_qs, cache_key=cache_key)

        paginator = Paginator(qs, filters["page_size"])
        page = paginator.get_page(filters["page"])

        context.update({
            "active_menu": "reports",
            "report_type": "products",
            "summary": summary,
            "page_obj": page,
            "products": page.object_list,
            "date_presets": DATE_PRESETS,
            "filters": filters,
            "status_choices": Order.Status.choices,
            "payment_choices": Payment.Method.choices,
            "categories": Category.objects.filter(is_active=True).order_by("name"),
            "filter_products": Product.objects.filter(is_active=True).order_by("name")[:200],
            "sort": filters["sort"],
        })
        return context


# ---------------------------------------------------------------------------
# Customer Report
# ---------------------------------------------------------------------------

class CustomerReportView(StaffRequiredMixin, TemplateView):
    template_name = "admin/reports/report_customers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = _get_report_filters(self.request)
        qs = get_customer_report_queryset(filters)
        qs = _apply_sort_customers(qs, filters["sort"])

        order_qs = get_base_order_queryset()
        order_qs = apply_report_filters(order_qs, **_filter_kwargs_for_report(filters))
        from django.conf import settings as django_settings
        _f = _get_report_filters(self.request)
        _cache_params = {k: _f[k] for k in _f if k not in ("sort", "page", "page_size")}
        cache_key = report_cache_key("customers", **_cache_params) if getattr(django_settings, "CACHE_REPORT_SUMMARY", False) else None
        summary = get_report_summary(order_qs, cache_key=cache_key)

        paginator = Paginator(qs, filters["page_size"])
        page = paginator.get_page(filters["page"])

        context.update({
            "active_menu": "reports",
            "report_type": "customers",
            "summary": summary,
            "page_obj": page,
            "customers": page.object_list,
            "date_presets": DATE_PRESETS,
            "filters": filters,
            "status_choices": Order.Status.choices,
            "payment_choices": Payment.Method.choices,
            "sort": filters["sort"],
        })
        return context


# ---------------------------------------------------------------------------
# Inventory Report
# ---------------------------------------------------------------------------

class InventoryReportView(StaffRequiredMixin, TemplateView):
    template_name = "admin/reports/report_inventory.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = _get_report_filters(self.request)
        variants_qs = get_inventory_report_queryset(filters)
        variants = list(variants_qs[:500])

        context.update({
            "active_menu": "reports",
            "report_type": "inventory",
            "variants": variants,
            "filters": filters,
            "categories": Category.objects.filter(is_active=True).order_by("name"),
            "products": Product.objects.filter(is_active=True).order_by("name")[:200],
            "summary": {
                "total_orders": 0,
                "total_revenue": Decimal("0"),
                "avg_order_value": Decimal("0"),
                "top_product_name": "—",
            },
        })
        return context


# ---------------------------------------------------------------------------
# AJAX API: return JSON with summary + HTML table body + pagination
# ---------------------------------------------------------------------------

class ReportApiView(StaffRequiredMixin, View):
    """AJAX: GET with same filter params; returns JSON { summary, html, pagination }."""

    def get(self, request, report_type):
        if report_type not in ("orders", "sales", "products", "customers", "inventory"):
            return JsonResponse({"error": "Invalid report type"}, status=400)

        filters = _get_report_filters(request)
        summary = None
        html = ""
        pagination = {}

        if report_type in ("orders", "sales"):
            qs = get_orders_report_queryset(filters)
            qs = _apply_sort_orders(qs, filters["sort"])
            summary = get_report_summary(qs, cache_key=None)
            paginator = Paginator(qs, filters["page_size"])
            page = paginator.get_page(filters["page"])
            html = render(
                request,
                "admin/reports/partials/orders_table.html",
                {"orders": page.object_list, "status_choices": Order.Status.choices},
            ).content.decode("utf-8")
            pagination = {
                "page": page.number,
                "num_pages": paginator.num_pages,
                "total_count": paginator.count,
                "has_previous": page.has_previous(),
                "has_next": page.has_next(),
            }
        elif report_type == "products":
            qs = get_product_performance_queryset(filters)
            qs = _apply_sort_products(qs, filters["sort"])
            order_qs = get_base_order_queryset()
            order_qs = apply_report_filters(order_qs, **_filter_kwargs_for_report(filters))
            summary = get_report_summary(order_qs, cache_key=None)
            paginator = Paginator(qs, filters["page_size"])
            page = paginator.get_page(filters["page"])
            html = render(
                request,
                "admin/reports/partials/products_table.html",
                {"products": page.object_list},
            ).content.decode("utf-8")
            pagination = {
                "page": page.number,
                "num_pages": paginator.num_pages,
                "total_count": paginator.count,
                "has_previous": page.has_previous(),
                "has_next": page.has_next(),
            }
        elif report_type == "customers":
            qs = get_customer_report_queryset(filters)
            qs = _apply_sort_customers(qs, filters["sort"])
            order_qs = get_base_order_queryset()
            order_qs = apply_report_filters(order_qs, **_filter_kwargs_for_report(filters))
            summary = get_report_summary(order_qs, cache_key=None)
            paginator = Paginator(qs, filters["page_size"])
            page = paginator.get_page(filters["page"])
            html = render(
                request,
                "admin/reports/partials/customers_table.html",
                {"customers": page.object_list},
            ).content.decode("utf-8")
            pagination = {
                "page": page.number,
                "num_pages": paginator.num_pages,
                "total_count": paginator.count,
                "has_previous": page.has_previous(),
                "has_next": page.has_next(),
            }
        else:
            # inventory: no pagination in API for simplicity; return full table
            variants_qs = get_inventory_report_queryset(filters)
            variants = list(variants_qs[:200])
            summary = {"total_orders": 0, "total_revenue": 0, "avg_order_value": 0, "top_product_name": "—"}
            html = render(
                request,
                "admin/reports/partials/inventory_table.html",
                {"variants": variants},
            ).content.decode("utf-8")
            pagination = {"page": 1, "num_pages": 1, "total_count": 0, "has_previous": False, "has_next": False}

        # Serialize summary decimals
        if summary:
            summary = {
                "total_orders": summary["total_orders"],
                "total_revenue": str(summary["total_revenue"]),
                "avg_order_value": str(summary["avg_order_value"]),
                "top_product_name": summary["top_product_name"],
            }
        return JsonResponse({"summary": summary, "html": html, "pagination": pagination})


# ---------------------------------------------------------------------------
# Export: CSV (and Excel if openpyxl available)
# ---------------------------------------------------------------------------

class ReportExportView(StaffRequiredMixin, View):
    def get(self, request, report_type, format_type):
        if report_type not in ("orders", "sales", "products", "customers", "inventory"):
            return HttpResponse("Invalid report type", status=400)
        if format_type not in ("csv", "xlsx"):
            return HttpResponse("Invalid format", status=400)

        filters = _get_report_filters(request)
        # Export without pagination (limit to 10k for safety)
        filters["page_size"] = 10000
        filters["page"] = 1

        if format_type == "csv":
            return self._export_csv(request, report_type, filters)
        return self._export_xlsx(request, report_type, filters)

    def _export_csv(self, request, report_type, filters):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="report_{report_type}.csv"'
        writer = csv.writer(response)

        if report_type in ("orders", "sales"):
            qs = get_orders_report_queryset(filters)
            qs = _apply_sort_orders(qs, filters["sort"])[:10000]
            writer.writerow(["Order #", "Date", "Customer", "Phone", "Total", "Status", "Payment"])
            for o in qs:
                payment_method = ""
                try:
                    if hasattr(o, "payment") and o.payment:
                        payment_method = o.payment.get_method_display() or o.payment.method
                except Exception:
                    pass
                writer.writerow([
                    o.order_number,
                    o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
                    o.address.full_name if o.address else "",
                    o.address.phone if o.address else "",
                    o.total,
                    o.get_status_display(),
                    payment_method,
                ])
        elif report_type == "products":
            qs = get_product_performance_queryset(filters)
            qs = _apply_sort_products(qs, filters["sort"])[:10000]
            writer.writerow(["Product", "Category", "Units Sold", "Revenue", "Orders"])
            for p in qs:
                writer.writerow([
                    p.name,
                    p.category.name if p.category else "",
                    p.units_sold or 0,
                    p.revenue or 0,
                    p.order_count or 0,
                ])
        elif report_type == "customers":
            qs = get_customer_report_queryset(filters)
            qs = _apply_sort_customers(qs, filters["sort"])[:10000]
            writer.writerow(["User", "Email", "Orders", "Total Spent"])
            for u in qs:
                writer.writerow([
                    getattr(u, "username", ""),
                    getattr(u, "email", ""),
                    u.order_count or 0,
                    u.total_spent or 0,
                ])
        else:
            variants_qs = get_inventory_report_queryset(filters)
            writer.writerow(["Product", "Category", "Variant", "Stock", "SKU"])
            for v in variants_qs[:5000]:
                product_name = v.product.name if v.product else ""
                category_name = v.product.category.name if v.product and v.product.category else ""
                variant_label = v.get_attribute_values_display()
                writer.writerow([product_name, category_name, variant_label, v.stock_quantity, v.sku or ""])
        return response

    def _export_xlsx(self, request, report_type, filters):
        try:
            import openpyxl
        except ImportError:
            return HttpResponse("Excel export requires openpyxl. Install: pip install openpyxl", status=501)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report_type[:31]

        if report_type in ("orders", "sales"):
            qs = get_orders_report_queryset(filters)
            qs = _apply_sort_orders(qs, filters["sort"])[:10000]
            ws.append(["Order #", "Date", "Customer", "Phone", "Total", "Status", "Payment"])
            for o in qs:
                payment_method = ""
                try:
                    if hasattr(o, "payment") and o.payment:
                        payment_method = o.payment.get_method_display() or o.payment.method
                except Exception:
                    pass
                ws.append([
                    o.order_number,
                    o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
                    o.address.full_name if o.address else "",
                    o.address.phone if o.address else "",
                    float(o.total),
                    o.get_status_display(),
                    payment_method,
                ])
        elif report_type == "products":
            qs = get_product_performance_queryset(filters)
            qs = _apply_sort_products(qs, filters["sort"])[:10000]
            ws.append(["Product", "Category", "Units Sold", "Revenue", "Orders"])
            for p in qs:
                ws.append([
                    p.name,
                    p.category.name if p.category else "",
                    p.units_sold or 0,
                    float(p.revenue or 0),
                    p.order_count or 0,
                ])
        elif report_type == "customers":
            qs = get_customer_report_queryset(filters)
            qs = _apply_sort_customers(qs, filters["sort"])[:10000]
            ws.append(["User", "Email", "Orders", "Total Spent"])
            for u in qs:
                ws.append([
                    getattr(u, "username", ""),
                    getattr(u, "email", ""),
                    u.order_count or 0,
                    float(u.total_spent or 0),
                ])
        else:
            variants_qs = get_inventory_report_queryset(filters)
            ws.append(["Product", "Category", "Variant", "Stock", "SKU"])
            for v in list(variants_qs[:5000]):
                product_name = v.product.name if v.product else ""
                category_name = v.product.category.name if v.product and v.product.category else ""
                variant_label = v.get_attribute_values_display()
                ws.append([product_name, category_name, variant_label, v.stock_quantity, v.sku or ""])

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="report_{report_type}.xlsx"'
        return response
