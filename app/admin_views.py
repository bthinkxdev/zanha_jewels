import json
import logging
import time
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.db import connection, transaction
from django.db.models import Count, Max, Sum, Q, F, ProtectedError
from django.db.models.functions import TruncDate
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from .models import (
    Banner,
    CartItem,
    Category,
    ContactMessage,
    Order,
    OrderItem,
    Product,
    ProductAttributeValue,
    Review,
    Shipment,
    Variant,
    VariantImage,
)
from django.conf import settings

from .admin_forms import (
    AdminLoginForm,
    BannerForm,
    CategoryForm,
    ProductBasicEditForm,
    _validate_image_file,
)
from .utils.debug_trace import Trace
from .admin_product_edit_views import (
    ProductCreateBasicView as BaseProductCreateBasicView,
    ProductEditView as BaseProductEditView,
    ProductUpdateBasicView as BaseProductUpdateBasicView,
    ProductToggleActiveView as BaseProductToggleActiveView,
    ProductAttributesListApiView as BaseProductAttributesListApiView,
    ProductAttributeCreateApiView as BaseProductAttributeCreateApiView,
    ProductAttributesReorderApiView as BaseProductAttributesReorderApiView,
    ProductAttributeUpdateApiView as BaseProductAttributeUpdateApiView,
    ProductAttributeDeleteApiView as BaseProductAttributeDeleteApiView,
    ProductAttributeValueCreateApiView as BaseProductAttributeValueCreateApiView,
    ProductAttributeValuesReorderApiView as BaseProductAttributeValuesReorderApiView,
    ProductAttributeValueUpdateApiView as BaseProductAttributeValueUpdateApiView,
    ProductAttributeValueDeleteApiView as BaseProductAttributeValueDeleteApiView,
    ProductVariantsListApiView as BaseProductVariantsListApiView,
    VariantCreateApiView as BaseVariantCreateApiView,
    VariantUpdateApiView as BaseVariantUpdateApiView,
    VariantDeleteApiView as BaseVariantDeleteApiView,
    VariantUploadImageView as BaseVariantUploadImageView,
    VariantImageDeleteView as BaseVariantImageDeleteView,
    VariantImageSetPrimaryView as BaseVariantImageSetPrimaryView,
    VariantImageReorderView as BaseVariantImageReorderView,
    ProductImageUploadView as BaseProductImageUploadView,
    ProductImageDeleteView as BaseProductImageDeleteView,
    ProductImageSetPrimaryView as BaseProductImageSetPrimaryView,
    ProductImageReorderView as BaseProductImageReorderView,
)

logger = logging.getLogger(__name__)
from .services.shiprocket_service import (
    shiprocket_service,
    ShiprocketAPIError,
    create_shipment_for_order,
)
from .services import send_order_confirmation_email_async
from .delivery_utils import delivery_enabled

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff/admin access"""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect("admin_panel:login")
        messages.error(self.request, "You don't have permission to access this area.")
        return redirect("store:home")


# Product edit modular API (wrappers with StaffRequiredMixin)
class ProductCreateBasicView(StaffRequiredMixin, BaseProductCreateBasicView):
    """POST create-basic/ — staff only."""


class ProductEditView(StaffRequiredMixin, BaseProductEditView):
    pass


class ProductUpdateBasicView(StaffRequiredMixin, BaseProductUpdateBasicView):
    pass


class ProductToggleActiveView(StaffRequiredMixin, BaseProductToggleActiveView):
    pass


class ProductAttributesListApiView(StaffRequiredMixin, BaseProductAttributesListApiView):
    pass


class ProductAttributeCreateApiView(StaffRequiredMixin, BaseProductAttributeCreateApiView):
    pass


class ProductAttributesReorderApiView(StaffRequiredMixin, BaseProductAttributesReorderApiView):
    pass


class ProductAttributeUpdateApiView(StaffRequiredMixin, BaseProductAttributeUpdateApiView):
    pass


class ProductAttributeDeleteApiView(StaffRequiredMixin, BaseProductAttributeDeleteApiView):
    pass


class ProductAttributeValueCreateApiView(StaffRequiredMixin, BaseProductAttributeValueCreateApiView):
    pass


class ProductAttributeValuesReorderApiView(StaffRequiredMixin, BaseProductAttributeValuesReorderApiView):
    pass


class ProductAttributeValueUpdateApiView(StaffRequiredMixin, BaseProductAttributeValueUpdateApiView):
    pass


class ProductAttributeValueDeleteApiView(StaffRequiredMixin, BaseProductAttributeValueDeleteApiView):
    pass


class ProductVariantsListApiView(StaffRequiredMixin, BaseProductVariantsListApiView):
    pass


class VariantCreateApiView(StaffRequiredMixin, BaseVariantCreateApiView):
    pass


class VariantUpdateApiView(StaffRequiredMixin, BaseVariantUpdateApiView):
    pass


class VariantDeleteApiView(StaffRequiredMixin, BaseVariantDeleteApiView):
    pass


class VariantUploadImageView(StaffRequiredMixin, BaseVariantUploadImageView):
    pass


class VariantImageDeleteView(StaffRequiredMixin, BaseVariantImageDeleteView):
    pass


class VariantImageSetPrimaryView(StaffRequiredMixin, BaseVariantImageSetPrimaryView):
    pass


class VariantImageReorderView(StaffRequiredMixin, BaseVariantImageReorderView):
    pass


class ProductImageUploadView(StaffRequiredMixin, BaseProductImageUploadView):
    pass


class ProductImageDeleteView(StaffRequiredMixin, BaseProductImageDeleteView):
    pass


class ProductImageSetPrimaryView(StaffRequiredMixin, BaseProductImageSetPrimaryView):
    pass


class ProductImageReorderView(StaffRequiredMixin, BaseProductImageReorderView):
    pass


# Authentication Views
class AdminLoginView(View):
    template_name = "admin_panel/login.html"
    
    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect("admin_panel:dashboard")
        form = AdminLoginForm()
        return render(request, self.template_name, {"form": form})
    
    def post(self, request):
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)
            
            if user and user.is_staff:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("admin_panel:dashboard")
            else:
                messages.error(request, "Invalid credentials or insufficient permissions.")
        
        return render(request, self.template_name, {"form": form})


class AdminLogoutView(View):
    def post(self, request):
        logout(request)
        messages.success(request, "Logged out successfully.")
        return redirect("admin_panel:login")


# Dashboard View
class AdminDashboardView(StaffRequiredMixin, TemplateView):
    template_name = "admin/dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Date filters
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Order statistics
        total_orders = Order.objects.count()
        orders_today = Order.objects.filter(created_at__date=today).count()
        orders_this_week = Order.objects.filter(created_at__date__gte=last_7_days).count()
        orders_this_month = Order.objects.filter(created_at__date__gte=last_30_days).count()
        
        # Revenue statistics
        total_revenue = Order.objects.aggregate(total=Sum("total"))["total"] or 0
        revenue_today = Order.objects.filter(created_at__date=today).aggregate(total=Sum("total"))["total"] or 0
        revenue_this_week = Order.objects.filter(created_at__date__gte=last_7_days).aggregate(total=Sum("total"))["total"] or 0
        revenue_this_month = Order.objects.filter(created_at__date__gte=last_30_days).aggregate(total=Sum("total"))["total"] or 0
        
        # Order status breakdown
        order_status = Order.objects.values("status").annotate(count=Count("id"))
        
        # Product statistics (Variant-based)
        total_products = Product.objects.filter(is_active=True).count()
        low_stock_products = Variant.objects.filter(
            is_active=True,
            stock_quantity__lte=5,
            stock_quantity__gt=0
        ).count()
        out_of_stock_products = Variant.objects.filter(
            is_active=True,
            stock_quantity=0
        ).count()
        
        # Recent orders
        recent_orders = Order.objects.select_related("address").order_by("-created_at")[:10]
        
        # Top selling products (last 30 days): sum quantities from non-cancelled orders only
        top_rows = list(
            OrderItem.objects.filter(
                order__created_at__gte=last_30_days,
            )
            .exclude(order__status=Order.Status.CANCELLED)
            .values("product_id")
            .annotate(
                total_sold=Sum("quantity"),
                revenue=Sum(F("quantity") * F("unit_price")),
            )
            .order_by("-total_sold")[:5]
        )
        if top_rows:
            product_ids = [r["product_id"] for r in top_rows]
            products_by_id = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}
            top_products = []
            for r in top_rows:
                p = products_by_id.get(r["product_id"])
                if p:
                    top_products.append(
                        type("TopProductRow", (), {
                            "name": p.name,
                            "total_sold": r["total_sold"],
                            "revenue": r["revenue"] or 0,
                        })()
                    )
        else:
            top_products = []
        
        # Recent messages
        unresolved_messages = ContactMessage.objects.filter(is_resolved=False).count()
        
        # Daily revenue chart data (last 14 days)
        import json
        chart_data = []
        for i in range(13, -1, -1):
            date = today - timedelta(days=i)
            daily_revenue = Order.objects.filter(
                created_at__date=date
            ).aggregate(total=Sum("total"))["total"] or 0
            chart_data.append({
                "date": date.strftime("%d %b"),
                "revenue": float(daily_revenue)
            })
        chart_data_json = json.dumps(chart_data)
        
        context.update({
            "total_orders": total_orders,
            "orders_today": orders_today,
            "orders_this_week": orders_this_week,
            "orders_this_month": orders_this_month,
            "total_revenue": total_revenue,
            "revenue_today": revenue_today,
            "revenue_this_week": revenue_this_week,
            "revenue_this_month": revenue_this_month,
            "order_status": order_status,
            "total_products": total_products,
            "low_stock_products": low_stock_products,
            "out_of_stock_products": out_of_stock_products,
            "recent_orders": recent_orders,
            "top_products": top_products,
            "unresolved_messages": unresolved_messages,
            "chart_data": chart_data_json,
            "active_menu": "dashboard",
        })
        
        return context


# Category Management Views
class CategoryListView(StaffRequiredMixin, ListView):
    model = Category
    template_name = "admin/category_list.html"
    context_object_name = "categories"
    paginate_by = 20
    
    def get_queryset(self):
        qs = Category.objects.annotate(product_count=Count("products"))
        search = self.request.GET.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search))
        return qs.order_by("-created_at")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "categories"
        context["search_query"] = self.request.GET.get("search", "")
        return context


class CategoryCreateView(StaffRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "admin/category_form.html"
    success_url = reverse_lazy("admin_panel:category_list")
    
    def form_valid(self, form):
        messages.success(self.request, "Category created successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "categories"
        context["form_title"] = "Create Category"
        return context


class CategoryUpdateView(StaffRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "admin/category_form.html"
    success_url = reverse_lazy("admin_panel:category_list")
    
    def form_valid(self, form):
        messages.success(self.request, "Category updated successfully!")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "categories"
        context["form_title"] = "Edit Category"
        return context


class CategoryDeleteView(StaffRequiredMixin, DeleteView):
    model = Category
    success_url = reverse_lazy("admin_panel:category_list")
    
    def post(self, request, *args, **kwargs):
        """Override post to check for existing products before deleting"""
        self.object = self.get_object()
        
        if self.object.products.exists():
            messages.error(request, "Cannot delete category with existing products.")
            return redirect("admin_panel:category_list")
        
        success_url = self.get_success_url()
        category_name = self.object.name
        
        # Manually handle image deletion via storage backend
        if self.object.image:
            try:
                image_name = self.object.image.name
                storage = self.object.image.storage
                
                # Null the image field before deleting the file
                Category.objects.filter(pk=self.object.pk).update(image=None)
                
                # Delete the file from storage (works with both local and S3)
                try:
                    storage.delete(image_name)
                except Exception:
                    pass  # Ignore if file doesn't exist
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete category image: {str(e)}")
        
        # Delete the category object
        try:
            Category.objects.filter(pk=self.object.pk).delete()
            messages.success(request, f"Category '{category_name}' deleted successfully!")
        except Exception as e:
            messages.error(request, f"Error deleting category: {str(e)}")
            
        return redirect(success_url)


# Banner Management Views
class BannerListView(StaffRequiredMixin, ListView):
    model = Banner
    template_name = "admin/banner_list.html"
    context_object_name = "banners"
    paginate_by = 20

    def get_queryset(self):
        qs = Banner.objects.all()
        status = self.request.GET.get("status")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        return qs.order_by("display_order", "created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "banners"
        context["filter_status"] = self.request.GET.get("status", "")
        context["max_active"] = Banner.MAX_ACTIVE
        return context


class BannerCreateView(StaffRequiredMixin, CreateView):
    model = Banner
    form_class = BannerForm
    template_name = "admin/banner_form.html"
    success_url = reverse_lazy("admin_panel:banner_list")

    def form_valid(self, form):
        messages.success(self.request, "Banner created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "banners"
        context["form_title"] = "Create Banner"
        context["max_active"] = Banner.MAX_ACTIVE
        return context


class BannerUpdateView(StaffRequiredMixin, UpdateView):
    model = Banner
    form_class = BannerForm
    template_name = "admin/banner_form.html"
    success_url = reverse_lazy("admin_panel:banner_list")

    def form_valid(self, form):
        messages.success(self.request, "Banner updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "banners"
        context["form_title"] = "Edit Banner"
        context["max_active"] = Banner.MAX_ACTIVE
        return context


class BannerDeleteView(StaffRequiredMixin, DeleteView):
    model = Banner
    success_url = reverse_lazy("admin_panel:banner_list")

    def delete(self, request, *args, **kwargs):
        """Override delete to handle S3 image deletion properly"""
        self.object = self.get_object()
        success_url = self.get_success_url()
        
        # Manually handle S3 file deletion
        if self.object.image:
            try:
                # Store the image name for deletion
                image_name = self.object.image.name
                storage = self.object.image.storage
                
                # Update DB to NULL the image field before deletion
                Banner.objects.filter(pk=self.object.pk).update(image=None)
                
                # Delete the file from S3
                try:
                    storage.delete(image_name)
                except Exception:
                    pass  # Ignore if file doesn't exist
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete banner image: {str(e)}")
        
        # Delete the banner object (image field is already None in DB)
        try:
            Banner.objects.filter(pk=self.object.pk).delete()
            messages.success(request, "Banner deleted successfully!")
        except Exception as e:
            messages.error(request, f"Error deleting banner: {str(e)}")
            
        return redirect(success_url)


# Product Management Views
class ProductListView(StaffRequiredMixin, ListView):
    model = Product
    template_name = "admin/product_list.html"
    context_object_name = "products"
    paginate_by = 20
    
    def get_queryset(self):
        qs = Product.objects.select_related("category").prefetch_related("variants")
        search = self.request.GET.get("search")
        category = self.request.GET.get("category")
        status = self.request.GET.get("status")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if category:
            qs = qs.filter(category_id=category)
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "products"
        context["categories"] = Category.objects.filter(is_active=True)
        context["search_query"] = self.request.GET.get("search", "")
        context["filter_category"] = self.request.GET.get("category", "")
        context["filter_status"] = self.request.GET.get("status", "")
        for product in context["products"]:
            # Use helpers so both simple products and variant products are handled.
            product.inventory_count = product.get_stock()
            product.display_price = product.get_price()
        return context


class ProductCreateView(StaffRequiredMixin, TemplateView):
    """GET only. Renders create page. Create via AJAX (create-basic, then attributes/variants/images on edit)."""
    template_name = "admin/product_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "products"
        context["form_title"] = "Add Product"
        context["basic_form"] = ProductBasicEditForm(instance=None)
        return context


class ProductDeleteView(StaffRequiredMixin, DeleteView):
    model = Product
    success_url = reverse_lazy("admin_panel:product_list")

    def post(self, request, *args, **kwargs):
        """Override post to handle deletion with proper error handling."""
        self.object = self.get_object()
        product_name = self.object.name
        success_url = self.get_success_url()

        # Check if product itself is used in any order
        if OrderItem.objects.filter(product=self.object).exists():
            messages.error(
                request,
                f"Cannot delete product \"{product_name}\". It is linked to existing orders.",
            )
            return redirect(success_url)

        # Remove cart items for this product before deletion
        CartItem.objects.filter(product=self.object).delete()

        # Delete variant images from storage (VariantImage)
        for variant in self.object.variants.all():
            for img in variant.images.all():
                if img.image:
                    try:
                        image_name = img.image.name
                        storage = img.image.storage
                        VariantImage.objects.filter(pk=img.pk).update(image=None)
                        try:
                            storage.delete(image_name)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning("Failed to delete variant image: %s", str(e))

        # Delete the product and all related data
        try:
            self.object.delete()
            messages.success(request, f"Product \"{product_name}\" has been deleted successfully.")
        except ProtectedError as e:
            # This should not happen if our checks are correct, but handle it anyway
            messages.error(
                request,
                f"Cannot delete product \"{product_name}\". It is protected by existing order data.",
            )
        except Exception as e:
            messages.error(request, f"Could not delete product: {str(e)}")

        return redirect(success_url)


class ProductDeleteCheckView(StaffRequiredMixin, View):
    """Check if a product can be deleted and return deletion status"""
    
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        
        # Check if product has any orders at all
        all_orders = Order.objects.filter(
            items__product=product
        ).distinct()
        
        # Check if product has any active orders (not delivered or cancelled)
        active_orders = all_orders.exclude(
            status__in=["delivered", "cancelled"]
        ).distinct()
        
        if active_orders.exists():
            # Cannot delete - has active orders
            return JsonResponse({
                'can_delete': False,
                'has_active_orders': True,
                'has_orders': True,
                'message': f'Cannot delete: {active_orders.count()} active order(s)'
            })
        
        if not all_orders.exists():
            # Can completely delete - no orders
            return JsonResponse({
                'can_delete': True,
                'will_delete_completely': True,
                'has_orders': False,
                'message': 'Product will be completely deleted'
            })
        
        # Can deactivate - all orders are delivered/cancelled
        return JsonResponse({
            'can_delete': True,
            'will_delete_completely': False,
            'has_orders': True,
            'message': 'Product will be set to inactive'
        })


# Order Management Views
class OrderListView(StaffRequiredMixin, ListView):
    model = Order
    template_name = "admin/order_list.html"
    context_object_name = "orders"
    paginate_by = 20
    
    def get_queryset(self):
        qs = Order.objects.select_related("address").prefetch_related("items")
        search = self.request.GET.get("search")
        status = self.request.GET.get("status")
        
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search) |
                Q(address__full_name__icontains=search) |
                Q(address__phone__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        
        return qs.order_by("-created_at")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "orders"
        context["search_query"] = self.request.GET.get("search", "")
        context["filter_status"] = self.request.GET.get("status", "")
        context["status_choices"] = Order.Status.choices
        return context


class OrderDetailView(StaffRequiredMixin, DetailView):
    model = Order
    template_name = "admin/order_detail.html"
    context_object_name = "order"
    slug_field = "order_number"
    slug_url_kwarg = "order_number"
    
    def get_queryset(self):
        return Order.objects.select_related("address", "payment").prefetch_related(
            "items__product", "items__selected_variant"
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "orders"
        context["status_choices"] = Order.Status.choices
        context["shipment"] = getattr(self.object, "shipment", None)
        return context


class OrderInvoiceView(StaffRequiredMixin, DetailView):
    """Professional A4 Invoice view for printing"""
    model = Order
    template_name = "admin/order_invoice.html"
    context_object_name = "order"
    slug_field = "order_number"
    slug_url_kwarg = "order_number"
    
    def get_queryset(self):
        return Order.objects.select_related("address", "payment").prefetch_related(
            "items__product", "items__selected_variant"
        )


class OrderUpdateStatusView(StaffRequiredMixin, View):
    def post(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number)
        new_status = request.POST.get("status")
        old_status = order.status
        
        if new_status not in dict(Order.Status.choices):
            messages.error(request, "Invalid status.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        # Prevent cancelling delivered orders
        if new_status == Order.Status.CANCELLED and order.status == Order.Status.DELIVERED:
            messages.error(request, "Cannot cancel an order that has already been delivered.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        # If moving to cancelled and shipment exists, attempt Shiprocket cancellation
        if new_status == Order.Status.CANCELLED:
            shipment = getattr(order, "shipment", None)
            if shipment and not shipment.is_cancelled:
                try:
                    shiprocket_service.cancel_shipment(shipment)
                    shipment.is_cancelled = True
                    shipment.cancelled_at = timezone.now()
                    shipment.current_status = "cancelled"
                    shipment.save(update_fields=["is_cancelled", "cancelled_at", "current_status", "updated_at"])
                except ShiprocketAPIError as exc:
                    messages.error(request, f"Failed to cancel shipment in Shiprocket: {exc}")
                    return redirect("admin_panel:order_detail", order_number=order_number)
                except Exception as exc:
                    logger.error(
                        "Unexpected error cancelling shipment for order %s via status update: %s",
                        order_number,
                        exc,
                        exc_info=True,
                    )
                    messages.error(request, "Unexpected error while cancelling shipment.")
                    return redirect("admin_panel:order_detail", order_number=order_number)

        order.status = new_status
        order.save(update_fields=["status"])
        messages.success(request, f"Order status updated to {order.get_status_display()}.")

        # Customer notification on key status changes (best-effort, async)
        try:
            if new_status in (
                Order.Status.CONFIRMED,
                Order.Status.SHIPPED,
                Order.Status.DELIVERED,
                Order.Status.CANCELLED,
            ) and new_status != old_status:
                send_order_confirmation_email_async(order)
        except Exception:
            pass
        
        return redirect("admin_panel:order_detail", order_number=order_number)


def _normalize_tracking_response(data):
    """
    Normalize Shiprocket track-by-AWB API response into our tracking_data shape
    (status, eta, activities) for storage on Shipment.tracking_data.
    """
    out = {"status": "", "eta": "", "activities": []}
    if not data:
        return out
    # Response can be { "tracking_data": { "shipment_track": [ {...} ] } } or similar
    tracking_data = data.get("tracking_data") or data
    shipment_tracks = tracking_data.get("shipment_track") or []
    if isinstance(shipment_tracks, dict):
        shipment_tracks = [shipment_tracks]
    if not shipment_tracks:
        out["status"] = (
            tracking_data.get("current_status")
            or data.get("current_status")
            or ""
        )
        out["eta"] = (
            tracking_data.get("etd")
            or tracking_data.get("eta")
            or tracking_data.get("estimated_delivery_date")
            or ""
        )
        out["activities"] = (
            tracking_data.get("shipment_track_activities")
            or tracking_data.get("activities")
            or tracking_data.get("tracking_history")
            or []
        )
        return out
    first = shipment_tracks[0] if shipment_tracks else {}
    out["status"] = (
        first.get("current_status")
        or first.get("status")
        or tracking_data.get("current_status")
        or ""
    )
    out["eta"] = (
        first.get("etd")
        or first.get("eta")
        or first.get("estimated_delivery_date")
        or ""
    )
    raw_activities = (
        first.get("shipment_track_activities")
        or first.get("activities")
        or first.get("tracking_history")
        or []
    )
    for a in raw_activities:
        if isinstance(a, dict):
            out["activities"].append({
                "date": a.get("date") or a.get("event_date") or a.get("timestamp") or "",
                "activity": a.get("activity") or a.get("status") or a.get("description") or "",
                "location": a.get("location") or a.get("city") or "",
            })
        else:
            out["activities"].append({"date": "", "activity": str(a), "location": ""})
    return out


class OrderShipmentRefreshTrackingView(StaffRequiredMixin, View):
    """POST: fetch latest tracking from Shiprocket by AWB and update shipment."""

    def post(self, request, order_number):
        if not delivery_enabled():
            messages.error(request, "Shipment tracking is disabled.")
            return redirect("admin_panel:order_detail", order_number=order_number)
        order = get_object_or_404(Order, order_number=order_number)
        shipment = getattr(order, "shipment", None)

        if not shipment:
            messages.error(request, "No shipment found for this order.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        if shipment.is_cancelled:
            messages.error(request, "Cannot refresh tracking for a cancelled shipment.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        if not shipment.awb_code:
            messages.error(request, "No AWB code available to track.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        try:
            data = shiprocket_service.track_shipment(shipment.awb_code)
            tracking = _normalize_tracking_response(data)
            shipment.current_status = tracking.get("status") or shipment.current_status
            shipment.tracking_data = {
                "status": tracking.get("status"),
                "eta": tracking.get("eta"),
                "activities": tracking.get("activities"),
                "awb_code": shipment.awb_code,
                "order_id": order_number,
            }
            shipment.save(update_fields=["current_status", "tracking_data", "updated_at"])
            messages.success(request, "Tracking data updated from Shiprocket.")
        except ShiprocketAPIError as exc:
            messages.error(request, f"Failed to fetch tracking: {exc}")
        except Exception as exc:
            logger.error(
                "Unexpected error refreshing tracking for order %s: %s",
                order_number,
                exc,
                exc_info=True,
            )
            messages.error(request, "An error occurred while refreshing tracking.")

        return redirect("admin_panel:order_detail", order_number=order_number)


# Contact Messages Management
class MessageListView(StaffRequiredMixin, ListView):
    model = ContactMessage
    template_name = "admin/message_list.html"
    context_object_name = "contact_messages"
    paginate_by = 20
    
    def get_queryset(self):
        qs = ContactMessage.objects.all()
        status = self.request.GET.get("status")
        
        if status == "unresolved":
            qs = qs.filter(is_resolved=False)
        elif status == "resolved":
            qs = qs.filter(is_resolved=True)
        
        return qs.order_by("-created_at")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "messages"
        context["filter_status"] = self.request.GET.get("status", "")
        return context


class MessageToggleResolvedView(StaffRequiredMixin, View):
    def post(self, request, pk):
        message = get_object_or_404(ContactMessage, pk=pk)
        message.is_resolved = not message.is_resolved
        message.save(update_fields=["is_resolved"])
        
        status_text = "resolved" if message.is_resolved else "unresolved"
        messages.success(request, f"Message marked as {status_text}.")
        
        return redirect("admin_panel:message_list")


class S3FileUploadView(StaffRequiredMixin, View):
    """Handle direct S3 file uploads via AJAX"""
    
    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Check if file is in request
            if 'file' not in request.FILES:
                return JsonResponse({
                    'success': False,
                    'error': 'No file provided'
                }, status=400)
            
            file = request.FILES['file']
            upload_path = request.POST.get('upload_path', 'uploads')
            
            logger.info(f"Uploading file: {file.name}, size: {file.size}, type: {file.content_type}")
            
            # Validate file size (5MB max)
            max_size = 5 * 1024 * 1024  # 5MB
            if file.size > max_size:
                return JsonResponse({
                    'success': False,
                    'error': f'File size exceeds 5MB limit. Current size: {file.size / (1024*1024):.2f}MB'
                }, status=400)
            
            # Validate image file
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if file.content_type not in allowed_types:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid file type. Allowed: JPG, PNG, GIF, WebP'
                }, status=400)
            
            # Save file using Django's storage backend (will use S3 if configured)
            from django.core.files.storage import default_storage
            from django.utils.text import slugify
            from django.conf import settings
            import os
            from datetime import datetime
            
            # Generate unique filename
            ext = os.path.splitext(file.name)[1].lower()
            base_name = slugify(os.path.splitext(file.name)[0])
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{base_name}_{timestamp}{ext}"
            file_path = f"{upload_path}/{filename}"
            
            logger.info(f"Saving to: {file_path}")
            
            # Upload to S3 with explicit ACL
            if settings.USE_S3:
                # For S3, use the configured storage (no ACL needed, bucket policy handles access)
                from custom_storage import MediaFileStorage
                storage = MediaFileStorage()
                saved_path = storage.save(file_path, file)
                file_url = storage.url(saved_path)
            else:
                saved_path = default_storage.save(file_path, file)
                file_url = default_storage.url(saved_path)
            
            logger.info(f"File saved to: {saved_path}")
            logger.info(f"File URL: {file_url}")
            
            # Verify the file exists
            if settings.USE_S3:
                exists = storage.exists(saved_path)
            else:
                exists = default_storage.exists(saved_path)
                
            if not exists:
                logger.error(f"File not found after upload: {saved_path}")
                return JsonResponse({
                    'success': False,
                    'error': 'Upload failed - file not found after upload'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'file_path': saved_path,
                'file_url': file_url,
                'file_name': filename,
                'file_size': file.size
            })
            
        except Exception as e:
            logger.error(f"Upload error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Upload failed: {str(e)}'
            }, status=500)


class DealOfDayListView(StaffRequiredMixin, TemplateView):
    """Admin view to manage Deal Of The Day products separately from the product form."""
    template_name = "admin/deals_list.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Optionally lock this screen based on the HOME_DEAL_OF_DAY_ENABLED flag
        so that when the feature is disabled in settings, the menu item is
        hidden and direct URL access is redirected.
        """
        if not getattr(settings, "HOME_DEAL_OF_DAY_ENABLED", True):
            messages.error(request, "Deal Of The Day management is disabled in settings.")
            return redirect("admin_panel:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Product.objects.select_related("category").order_by(
            "category__name", "name"
        )
        search = (self.request.GET.get("q") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(category__name__icontains=search)
            )
        current_only = self.request.GET.get("current")
        if current_only == "1":
            today = timezone.now().date()
            # Filter for products that are marked as deal and are currently active
            qs = qs.filter(
                Q(
                    is_deal_of_day=True,
                    deal_of_day_start__lte=today,
                    deal_of_day_end__gte=today,
                )
                | Q(
                    is_deal_of_day=True,
                    deal_of_day_start__isnull=True,
                    deal_of_day_end__isnull=True,
                )
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        paginator = Paginator(qs, 20)
        page = self.request.GET.get("page")
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context["active_menu"] = "deals"
        context["products"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["paginator"] = paginator
        context["is_paginated"] = paginator.num_pages > 1
        context["search_query"] = (self.request.GET.get("q") or "").strip()
        today = timezone.now().date()
        context["today"] = today
        context["filter_current"] = self.request.GET.get("current") == "1"
        
        # Count current active deals for badge
        if context["filter_current"]:
            context["active_deals_count"] = paginator.count
        else:
            # Count total current deals even when filter is off
            current_deals_qs = Product.objects.filter(
                Q(
                    is_deal_of_day=True,
                    deal_of_day_start__lte=today,
                    deal_of_day_end__gte=today,
                )
                | Q(
                    is_deal_of_day=True,
                    deal_of_day_start__isnull=True,
                    deal_of_day_end__isnull=True,
                )
            )
            context["active_deals_count"] = current_deals_qs.count()
        
        return context

    def post(self, request, *args, **kwargs):
        """Bulk update deal-of-day flags and date ranges for products."""
        products = self.get_queryset()
        updated_count = 0

        for product in products:
            prefix = f"p{product.pk}_"
            is_deal_flag = request.POST.get(f"is_deal_{product.pk}") == "on"
            start_raw = request.POST.get(f"start_{product.pk}") or ""
            end_raw = request.POST.get(f"end_{product.pk}") or ""

            start_date = parse_date(start_raw) if start_raw else None
            end_date = parse_date(end_raw) if end_raw else None

            changed = (
                product.is_deal_of_day != is_deal_flag
                or product.deal_of_day_start != start_date
                or product.deal_of_day_end != end_date
            )
            if not changed:
                continue

            product.is_deal_of_day = is_deal_flag
            product.deal_of_day_start = start_date
            product.deal_of_day_end = end_date
            product.save(update_fields=["is_deal_of_day", "deal_of_day_start", "deal_of_day_end"])
            updated_count += 1

        if updated_count:
            messages.success(request, f"Updated deals for {updated_count} product(s).")
        else:
            messages.info(request, "No changes were made.")

        return redirect("admin_panel:deal_list")


class ReviewListView(StaffRequiredMixin, TemplateView):
    """
    Professional admin moderation panel for Ratings & Reviews.

    Features:
    - Filters: product, rating, date range, approval status.
    - Search: by user (username/email) and product name.
    - Bulk actions: approve, unapprove, delete (soft delete).
    - Pagination.
    """

    template_name = "admin/review_list.html"
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "REVIEW_ENABLED", True):
            raise Http404("Reviews are not enabled.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Review.objects.select_related("product", "user", "order").filter(
            is_deleted=False
        )

        request = self.request
        q = (request.GET.get("q") or "").strip()
        product_id = request.GET.get("product")
        rating = request.GET.get("rating")
        status = request.GET.get("status")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")

        if q:
            qs = qs.filter(
                Q(product__name__icontains=q)
                | Q(user__username__icontains=q)
                | Q(user__email__icontains=q)
            )
        if product_id:
            try:
                qs = qs.filter(product_id=int(product_id))
            except (TypeError, ValueError):
                pass
        if rating:
            try:
                qs = qs.filter(rating=int(rating))
            except (TypeError, ValueError):
                pass
        if status == "approved":
            qs = qs.filter(is_approved=True)
        elif status == "unapproved":
            qs = qs.filter(is_approved=False)

        if date_from:
            try:
                df = parse_date(date_from)
                if df:
                    qs = qs.filter(created_at__date__gte=df)
            except Exception:
                pass
        if date_to:
            try:
                dt = parse_date(date_to)
                if dt:
                    qs = qs.filter(created_at__date__lte=dt)
            except Exception:
                pass

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_number = self.request.GET.get("page")
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context["active_menu"] = "reviews"
        context["reviews"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["paginator"] = paginator
        context["is_paginated"] = paginator.num_pages > 1

        context["products"] = Product.objects.order_by("name").only("id", "name")
        context["filter_q"] = (self.request.GET.get("q") or "").strip()
        context["filter_product"] = self.request.GET.get("product") or ""
        context["filter_rating"] = self.request.GET.get("rating") or ""
        context["filter_status"] = self.request.GET.get("status") or ""
        context["filter_date_from"] = self.request.GET.get("date_from") or ""
        context["filter_date_to"] = self.request.GET.get("date_to") or ""

        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        Handle bulk moderation actions:
        - approve
        - unapprove
        - delete (soft delete)
        """
        action = request.POST.get("action")
        ids = request.POST.getlist("selected")
        if not action or not ids:
            messages.warning(request, "Please select at least one review and an action.")
            return redirect("admin_panel:review_list")

        try:
            ids_int = [int(x) for x in ids]
        except (TypeError, ValueError):
            messages.error(request, "Invalid review selection.")
            return redirect("admin_panel:review_list")

        reviews = list(
            Review.objects.select_for_update()
            .select_related("product")
            .filter(id__in=ids_int)
        )
        if not reviews:
            messages.info(request, "No reviews found for the selected IDs.")
            return redirect("admin_panel:review_list")

        updated_products = set()

        if action == "approve":
            for r in reviews:
                if not r.is_approved and not r.is_deleted:
                    r.is_approved = True
                    r.save(update_fields=["is_approved"])
                    updated_products.add(r.product_id)
            messages.success(request, "Selected reviews have been approved.")
        elif action == "unapprove":
            for r in reviews:
                if r.is_approved and not r.is_deleted:
                    r.is_approved = False
                    r.save(update_fields=["is_approved"])
                    updated_products.add(r.product_id)
            messages.success(request, "Selected reviews have been unapproved.")
        elif action == "delete":
            for r in reviews:
                if not r.is_deleted:
                    r.is_deleted = True
                    r.save(update_fields=["is_deleted"])
                    updated_products.add(r.product_id)
            messages.success(request, "Selected reviews have been deleted.")
        else:
            messages.error(request, "Unknown action.")
            return redirect("admin_panel:review_list")

        # Product aggregates are kept in sync by Review model signals
        return redirect("admin_panel:review_list")

class ShipmentRetryView(StaffRequiredMixin, View):
    def post(self, request, order_number):
        if not delivery_enabled():
            messages.error(request, "Shipment creation is disabled.")
            return redirect("admin_panel:order_detail", order_number=order_number)
        order = get_object_or_404(Order, order_number=order_number)
        shipment = getattr(order, "shipment", None)

        if order.status == Order.Status.DELIVERED:
            messages.error(request, "Cannot recreate shipment for a delivered order.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        if shipment is None:
            shipment = Shipment.objects.create(order=order, current_status="pending_creation")

        try:
            create_shipment_for_order(order, shipment)
            messages.success(request, "Shipment successfully (re)created with Shiprocket.")
        except ShiprocketAPIError as exc:
            shipment.error_log = str(exc)
            shipment.current_status = "error"
            shipment.save(update_fields=["error_log", "current_status", "updated_at"])
            messages.error(request, f"Shiprocket error while creating shipment: {exc}")
        except Exception as exc:
            shipment.error_log = str(exc)
            shipment.current_status = "error"
            shipment.save(update_fields=["error_log", "current_status", "updated_at"])
            logger.error(
                "Unexpected error in ShipmentRetryView for order %s: %s",
                order_number,
                exc,
                exc_info=True,
            )
            messages.error(request, "Unexpected error while creating shipment.")

        return redirect("admin_panel:order_detail", order_number=order_number)


class ShipmentCancelView(StaffRequiredMixin, View):
    def post(self, request, order_number):
        if not delivery_enabled():
            messages.error(request, "Shipment cancellation is disabled.")
            return redirect("admin_panel:order_detail", order_number=order_number)
        order = get_object_or_404(Order, order_number=order_number)
        shipment = getattr(order, "shipment", None)

        if not shipment:
            messages.error(request, "No shipment found for this order.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        if order.status == Order.Status.DELIVERED:
            messages.error(request, "Cannot cancel a delivered order.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        if shipment.is_cancelled:
            messages.info(request, "Shipment is already marked as cancelled.")
            return redirect("admin_panel:order_detail", order_number=order_number)

        try:
            shiprocket_service.cancel_shipment(shipment)
            shipment.is_cancelled = True
            shipment.cancelled_at = timezone.now()
            shipment.current_status = "cancelled"
            shipment.save(update_fields=["is_cancelled", "cancelled_at", "current_status", "updated_at"])

            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])

            messages.success(request, "Shipment cancelled and order marked as cancelled.")
        except ShiprocketAPIError as exc:
            messages.error(request, f"Failed to cancel shipment in Shiprocket: {exc}")
        except Exception as exc:
            logger.error(
                "Unexpected error cancelling shipment for order %s: %s",
                order_number,
                exc,
                exc_info=True,
            )
            messages.error(request, "Unexpected error while cancelling shipment.")

        return redirect("admin_panel:order_detail", order_number=order_number)