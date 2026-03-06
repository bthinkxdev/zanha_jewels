from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q, F, Sum, Count, Min
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView, View
from django.utils import timezone

import json
import razorpay
import hmac
import hashlib

import logging
logger = logging.getLogger(__name__)

from .auth_decorators import LoginRequiredForActionMixin
from .forms import CartAddForm, CartUpdateForm, CheckoutForm, ContactForm, NewsletterForm, ReviewForm
from .models import (
    Banner,
    CartItem,
    Category,
    Order,
    OrderItem,
    Payment,
    Product,
    Review,
    Variant,
    Cart,
    Wishlist,
    Shipment,
)
from .services import CartError, CartService, OrderService, StockError

# Guest wishlist: session key and max items (variant ids)
GUEST_WISHLIST_SESSION_KEY = "wishlist"
GUEST_WISHLIST_MAX_ITEMS = 50


def _get_guest_wishlist_ids(request):
    """Return list of variant ids from session (guest wishlist)."""
    ids = request.session.get(GUEST_WISHLIST_SESSION_KEY) or []
    out = []
    seen = set()
    for x in ids:
        try:
            vid = int(x)
            if 0 < vid and vid not in seen:
                seen.add(vid)
                out.append(vid)
        except (TypeError, ValueError):
            continue
    return out[:GUEST_WISHLIST_MAX_ITEMS]


def _set_guest_wishlist_ids(request, ids):
    """Store list of variant ids in session (max GUEST_WISHLIST_MAX_ITEMS)."""
    request.session[GUEST_WISHLIST_SESSION_KEY] = ids[:GUEST_WISHLIST_MAX_ITEMS]


def _active_variant_qs():
    """Base queryset for Variant with product and images."""
    return (
        Variant.objects.filter(
            is_active=True,
            product__is_active=True,
            stock_quantity__gt=0,
        )
        .select_related("product", "product__category")
        .prefetch_related("images")
    )


def _collection_card_items(request, paginate_by=12):
    """
    Return list of (variant, False) for collection. One card per product: first in-stock Variant per product.
    """
    category = request.GET.get("category")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    query = request.GET.get("q")
    sort = (request.GET.get("sort") or "").strip().lower()

    qs = _active_variant_qs()
    if category and category != "all":
        qs = qs.filter(product__category__slug=category)
    if min_price:
        qs = qs.filter(price__gte=min_price)
    if max_price:
        qs = qs.filter(price__lte=max_price)
    if query:
        qs = qs.filter(
            Q(product__name__icontains=query)
            | Q(product__description__icontains=query)
            | Q(product__category__name__icontains=query)
        )
    if sort == "price_asc":
        qs = qs.order_by("price", "product__created_at")
    elif sort == "price_desc":
        qs = qs.order_by("-price", "-product__created_at")
    else:
        qs = qs.order_by("-product__created_at", "display_order", "id")

    seen_products = set()
    cards = []
    for v in qs:
        if v.product_id in seen_products:
            continue
        seen_products.add(v.product_id)
        cards.append((v, False))
    return cards


class ProductListView(ListView):
    """Collection page. One card per product (first in-stock variant)."""

    template_name = "shop.html"
    context_object_name = "card_items"
    paginate_by = 12

    def get_queryset(self):
        try:
            return _collection_card_items(self.request, self.paginate_by)
        except Exception as e:
            logger.error(f"Error in ProductListView.get_queryset: {str(e)}", exc_info=True)
            return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)
        context["products"] = context.get("card_items", [])
        context["page_title"] = "Shop All Products"
        context["active_page"] = "collection"
        category_slug = self.request.GET.get("category")
        if category_slug and category_slug != "all":
            category = Category.objects.filter(slug=category_slug).first()
            if category:
                context["page_title"] = category.name
        context["filters"] = {
            "category": self.request.GET.get("category", "all"),
            "min_price": self.request.GET.get("min_price", ""),
            "max_price": self.request.GET.get("max_price", ""),
            "q": self.request.GET.get("q", ""),
            "sort": self.request.GET.get("sort", "newest"),
        }
        context["sort_options"] = [
            ("newest", "Newest"),
            ("price_asc", "Price: Low to High"),
            ("price_desc", "Price: High to Low"),
        ]
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render(request, "partials/product_cards_gadget.html", context)
        return self.render_to_response(context)


class HomeView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            today = timezone.now().date()

            # --- Shop by Category (only categories with at least one sellable product) ---
            shop_categories_qs = (
                Category.objects.filter(
                    is_active=True,
                    products__is_active=True,
                    products__variants__is_active=True,
                    products__variants__stock_quantity__gt=0,
                )
                .distinct()
                .order_by("name")[:8]
            )
            context["shop_categories"] = list(shop_categories_qs)

            # --- Base product queryset for homepage sections (sellable products only) ---
            sellable_variants_qs = (
                Variant.objects.filter(
                    is_active=True,
                    stock_quantity__gt=0,
                )
                .prefetch_related("images")
                .order_by("display_order", "id")
            )

            base_products_qs = (
                Product.objects.available()
                .select_related("category")
                .prefetch_related(
                    Prefetch(
                        "variants",
                        queryset=sellable_variants_qs,
                        to_attr="sellable_variants",
                    )
                )
            )

            def _build_product_cards(qs, limit):
                """
                Attach primary_variant and lowest_price to each Product using prefetched variants.
                Returns a list of products limited to `limit`.
                """
                products = []
                for product in qs[:limit]:
                    variants = list(getattr(product, "sellable_variants", []) or [])
                    if not variants:
                        continue
                    # Choose primary variant by lowest price, then display_order, then id
                    primary_variant = min(
                        variants,
                        key=lambda v: (v.price, v.display_order, v.id),
                    )
                    product.primary_variant = primary_variant
                    product.lowest_price = primary_variant.price
                    products.append(product)
                return products

            # --- Deal of the Day ---
            deal_qs = base_products_qs.filter(is_deal_of_day=True)
            deal_qs = deal_qs.filter(
                Q(deal_of_day_start__isnull=True) | Q(deal_of_day_start__lte=today),
                Q(deal_of_day_end__isnull=True) | Q(deal_of_day_end__gte=today),
            ).order_by("-created_at")
            deal_of_day_products = _build_product_cards(deal_qs, 8)
            context["deal_of_day_products"] = deal_of_day_products
            # Backwards compatibility (older templates may still expect this key)
            context["deal_products"] = deal_of_day_products

            # --- Best Sellers ---
            bestseller_qs = base_products_qs.filter(is_bestseller=True).order_by(
                "-created_at"
            )
            context["bestseller_products"] = _build_product_cards(bestseller_qs, 8)

            # --- New Arrivals ---
            new_arrivals_qs = base_products_qs.order_by("-created_at")
            context["new_arrival_products"] = _build_product_cards(
                new_arrivals_qs, 8
            )

            # --- Top Rated ---
            top_rated_qs = base_products_qs.filter(
                average_rating__gte=4,
                total_reviews__gt=0,
            ).order_by("-average_rating", "-total_reviews", "-created_at")
            context["top_rated_products"] = _build_product_cards(top_rated_qs, 8)

            # --- Budget Picks (₹499 and under, ordered by lowest variant price) ---
            budget_qs = (
                Product.objects.available()
                .filter(variants__price__lte=499)
                .annotate(min_price=Min("variants__price"))
                .select_related("category")
                .prefetch_related(
                    Prefetch(
                        "variants",
                        queryset=sellable_variants_qs,
                        to_attr="sellable_variants",
                    )
                )
                .order_by("min_price", "-created_at")
                .distinct()
            )
            context["budget_products"] = _build_product_cards(budget_qs, 8)

            # --- Featured Collection ---
            featured_qs = base_products_qs.filter(is_featured=True).order_by(
                "-created_at"
            )
            context["featured_products"] = _build_product_cards(featured_qs, 8)

            active_banners = list(
                Banner.objects.filter(is_active=True).order_by("display_order", "created_at")
            )
            context["banners"] = [b for b in active_banners if b.image]
            context["active_page"] = "home"

            # --- Cart preview (home page) ---
            try:
                cart = CartService.get_or_create_cart(self.request)
                items_qs = cart.items.select_related(
                    "product",
                    "selected_variant",
                ).prefetch_related(
                    "selected_variant__images",
                )
                home_cart_items = list(items_qs)
                if home_cart_items:
                    totals = CartService.compute_totals(cart)
                    context["home_cart"] = cart
                    context["home_cart_items"] = home_cart_items
                    context["home_cart_totals"] = totals
                else:
                    context["home_cart_items"] = []
            except Exception as cart_exc:
                logger.error(f"Error building home cart preview: {cart_exc}", exc_info=True)
                context["home_cart_items"] = []

            # --- Wishlist: selected variants for Your Favorites ---
            home_wishlist_variants = []
            home_wishlist_products = []
            user = getattr(self.request, "user", None)
            if user and user.is_authenticated:
                try:
                    wishlist_items = list(
                        Wishlist.objects.filter(user=user)
                        .filter(
                            selected_variant__is_active=True,
                            selected_variant__product__is_active=True,
                        )
                        .select_related("selected_variant", "selected_variant__product", "selected_variant__product__category")
                        .prefetch_related("selected_variant__images")
                        .order_by("-created_at")[:12]
                    )
                    home_wishlist_variants = [wl.selected_variant for wl in wishlist_items if wl.selected_variant]
                except Exception as wl_exc:
                    logger.error(f"Error building home wishlist: {wl_exc}", exc_info=True)
            context["home_wishlist_variants"] = home_wishlist_variants
            context["home_wishlist_products"] = home_wishlist_products

            return context
        except Exception as e:
            logger.error(f"Error in HomeView.get_context_data: {str(e)}", exc_info=True)
            context = super().get_context_data(**kwargs)
            context["active_page"] = "home"
            context["shop_categories"] = []
            context["featured_products"] = []
            context["deal_of_day_products"] = []
            context["deal_products"] = []
            context["bestseller_products"] = []
            context["new_arrival_products"] = []
            context["top_rated_products"] = []
            context["budget_products"] = []
            context["banners"] = []
            context["home_wishlist_variants"] = []
            context["home_wishlist_products"] = []
            return context


RECENTLY_VIEWED_MAX = 20
RECENTLY_VIEWED_VARIANTS_MAX = 20


def _update_recently_viewed(session, product_id):
    """Update session with product_id: FIFO queue, max RECENTLY_VIEWED_MAX, no duplicates."""
    if not product_id:
        return
    ids = list(session.get("recently_viewed_ids", []))
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        return
    if pid in ids:
        ids.remove(pid)
    ids.append(pid)
    ids = ids[-RECENTLY_VIEWED_MAX:]
    session["recently_viewed_ids"] = ids
    session.modified = True


def _update_recently_viewed_variant(session, variant_id):
    """Update session with Variant ID: FIFO queue, max RECENTLY_VIEWED_VARIANTS_MAX."""
    if not variant_id:
        return
    ids = list(session.get("recently_viewed_variant_ids", []))
    try:
        vid = int(variant_id)
    except (TypeError, ValueError):
        return
    if vid in ids:
        ids.remove(vid)
    ids.append(vid)
    ids = ids[-RECENTLY_VIEWED_VARIANTS_MAX:]
    session["recently_viewed_variant_ids"] = ids
    session.modified = True


class ProductDetailView(DetailView):
    template_name = "product.html"
    context_object_name = "product"
    slug_url_kwarg = "slug"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        _update_recently_viewed(request.session, self.object.pk)
        variant_param = request.GET.get("variant")
        if variant_param:
            try:
                vid = int(variant_param)
                if Variant.objects.filter(pk=vid, product=self.object).exists():
                    _update_recently_viewed_variant(request.session, vid)
            except (TypeError, ValueError):
                pass
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Product.objects.active()
            .select_related("category")
            .prefetch_related(
                "attributes__values",
                Prefetch(
                    "variants",
                    queryset=Variant.objects.filter(
                        is_active=True,
                        stock_quantity__gt=0,
                    )
                    .prefetch_related(
                        "images",
                        "attribute_values__attribute",
                    )
                    .order_by("display_order", "id"),
                ),
            )
        )

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            product = context["product"]
            # Only sellable variants (active + stock > 0) for detail page + selection tree
            variants_qs = (
                product.variants.filter(
                    is_active=True,
                    stock_quantity__gt=0,
                )
                .prefetch_related("attribute_values__attribute", "images")
                .order_by("display_order", "id")
            )
            variants = list(variants_qs)

            # Selected variant: from ?variant= (if sellable) or first sellable
            selected_variant = None
            variant_param = self.request.GET.get("variant")
            if variant_param:
                try:
                    vid = int(variant_param)
                except (TypeError, ValueError):
                    vid = None
                if vid:
                    for v in variants:
                        if v.id == vid:
                            selected_variant = v
                            break
            if not selected_variant and variants:
                selected_variant = variants[0]

            # Only consider attribute values that actually appear on at least one sellable variant
            used_value_ids = set()
            for v in variants:
                for av_id in v.attribute_values.values_list("id", flat=True):
                    used_value_ids.add(av_id)

            # Attributes grouped for UI: [ { "name": "Case Color", "values": [{"id": 1, "value": "Black"}, ...] }, ... ]
            attributes_grouped = []
            for attr in product.attributes.prefetch_related("values").order_by("display_order", "name"):
                values_for_attr = [
                    {"id": av.id, "value": av.value}
                    for av in attr.values.order_by("display_order", "value")
                    if av.id in used_value_ids
                ]
                # Skip attributes with no values used by any active + in-stock variant
                if not values_for_attr:
                    continue
                attributes_grouped.append(
                    {
                        "id": attr.id,
                        "name": attr.name,
                        "values": values_for_attr,
                    }
                )
            context["variants"] = variants
            context["selected_variant"] = selected_variant
            context["attributes_grouped"] = attributes_grouped

            # Ordered attribute names for strict top-down selection (Level 0..N)
            context["ordered_attributes"] = [a["name"] for a in attributes_grouped]

            # Variant JSON for frontend (variant-driven, strict hierarchical selection)
            variant_json = []
            for v in variants:
                # Map attributes by human name: {"Color": "Blue", "Size": "XL"}
                attr_map = {}
                for av in v.attribute_values.select_related("attribute").all():
                    attr = getattr(av, "attribute", None)
                    if not attr or not attr.name:
                        continue
                    attr_map[attr.name] = av.value

                imgs = list(
                    v.images.filter(image__isnull=False)
                    .exclude(image="")
                    .order_by("-is_primary", "display_order", "id")
                )
                primary_image_url = None
                for img in imgs:
                    try:
                        if img.image and img.image.url:
                            primary_image_url = img.image.url
                            break
                    except Exception:
                        continue

                variant_json.append(
                    {
                        "id": v.id,
                        "price": str(v.price),
                        "stock": v.stock_quantity,
                        "attributes": attr_map,
                        "image": primary_image_url,
                        "is_gst_applicable": bool(product.is_gst_applicable),
                        "gst_percentage": str(product.gst_percentage) if product.is_gst_applicable and product.gst_percentage is not None else None,
                    }
                )
            context["variant_json"] = variant_json

            # GST display for product detail (initial selected variant)
            if selected_variant and getattr(product, "is_gst_applicable", False) and getattr(product, "gst_percentage", None) is not None:
                from decimal import Decimal
                gst_pct = product.gst_percentage
                base = selected_variant.price
                gst_amount = base * (gst_pct / Decimal("100"))
                context["product_detail_gst_amount"] = gst_amount
                context["product_detail_total_with_gst"] = base + gst_amount
                context["product_gst_percentage"] = gst_pct
            else:
                context["product_detail_gst_amount"] = None
                context["product_detail_total_with_gst"] = None
                context["product_gst_percentage"] = None

            selected_attr_value_ids = []
            if selected_variant:
                selected_attr_value_ids = list(
                    selected_variant.attribute_values.values_list("id", flat=True)
                )
            context["selected_attribute_value_ids"] = selected_attr_value_ids

            context["in_wishlist"] = False
            if self.request.user.is_authenticated and selected_variant:
                context["in_wishlist"] = Wishlist.objects.filter(
                    user=self.request.user, selected_variant=selected_variant
                ).exists()

            context["related_products"] = (
                Product.objects.active()
                .filter(category=product.category)
                .exclude(pk=product.pk)
                .select_related("category")
                .prefetch_related("variants__images")[:4]
            )
            context["similar_variants"] = [
                v for v in variants if selected_variant and v.id != selected_variant.id
            ][:12]
            context["add_form"] = CartAddForm(
                initial={
                    "product_id": product.id,
                    "variant_id": selected_variant.id if selected_variant else None,
                    "quantity": 1,
                }
            )
            context["active_page"] = "collection"
            context["selected_color_variant"] = selected_variant

            # ----- Ratings & Reviews (verified buyers only) -----
            reviews_qs = (
                Review.objects.filter(
                    product=product,
                    is_approved=True,
                    is_deleted=False,
                )
                .select_related("user", "order")
                .order_by("-created_at")
            )

            reviews_list = list(reviews_qs)
            total_reviews = product.total_reviews or 0

            average_rating = float(product.average_rating) if total_reviews > 0 else None

            # Star breakdown (5★..1★)
            breakdown_raw = reviews_qs.values("rating").annotate(count=Count("id"))
            rating_breakdown = {i: 0 for i in range(5, 0, -1)}
            for row in breakdown_raw:
                r = int(row["rating"])
                if 1 <= r <= 5:
                    rating_breakdown[r] = row["count"]

            # Precomputed rows for template (star, count, percent)
            breakdown_rows = []
            for star in range(5, 0, -1):
                count = rating_breakdown.get(star, 0)
                percent = int((count / total_reviews) * 100) if total_reviews else 0
                breakdown_rows.append(
                    {
                        "star": star,
                        "count": count,
                        "percent": percent,
                    }
                )

            # Can current user write a review?
            can_review = False
            user_review = None
            if self.request.user.is_authenticated:
                user_review = Review.objects.filter(
                    product=product,
                    user=self.request.user,
                ).first()
                if not user_review:
                    has_delivered_order = OrderItem.objects.filter(
                        order__user=self.request.user,
                        order__status=Order.Status.DELIVERED,
                        product=product,
                    ).exists()
                    can_review = has_delivered_order

            context["reviews"] = reviews_list
            context["average_rating"] = average_rating
            context["total_reviews"] = total_reviews
            context["rating_breakdown"] = rating_breakdown
            context["rating_breakdown_rows"] = breakdown_rows
            context["can_review"] = can_review
            context["user_review"] = user_review
            context["review_form"] = ReviewForm()

            return context
        except Exception as e:
            logger.error(f"Error in ProductDetailView.get_context_data: {str(e)}", exc_info=True)
            raise


class ProductReviewCreateView(LoginRequiredForActionMixin, View):
    """
    AJAX-only endpoint to create a product review from a verified buyer.

    Business rules:
    - Only logged-in users.
    - User must have at least one delivered order for the product.
    - One review per (product, user).
    - Rating 1–5.
    - Uses transaction.atomic to avoid race conditions with uniqueness.
    """

    http_method_names = ["post"]

    def post(self, request, product_id: int, *args, **kwargs):
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if not request.user.is_authenticated:
            login_url = f"{reverse('auth:login')}?next={request.build_absolute_uri()}"
            if is_ajax:
                return JsonResponse(
                    {
                        "success": False,
                        "login_required": True,
                        "login_url": login_url,
                        "error": "Login required to write a review.",
                    },
                    status=403,
                )
            return redirect(login_url)

        product = get_object_or_404(Product, pk=product_id, is_active=True)

        form = ReviewForm(request.POST)
        if not form.is_valid():
            if is_ajax:
                # Flatten errors
                error_text = "; ".join(
                    [f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()]
                ) or "Invalid review data."
                return JsonResponse(
                    {"success": False, "error": error_text},
                    status=400,
                )
            messages.error(request, "Invalid review data.")
            return redirect("store:product_detail", slug=product.slug)

        # Verify delivered order for this user and product
        delivered_qs = (
            OrderItem.objects.select_related("order")
            .filter(
                order__user=request.user,
                order__status=Order.Status.DELIVERED,
                product=product,
            )
            .order_by("-order__created_at")
        )
        delivered_item = delivered_qs.first()
        if not delivered_item:
            msg = "You can only review products you have received (delivered orders only)."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=403)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)

        # Prevent duplicate review
        if Review.objects.filter(product=product, user=request.user).exists():
            msg = "You have already reviewed this product."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)

        try:
            with transaction.atomic():
                Review.objects.create(
                    product=product,
                    user=request.user,
                    order=delivered_item.order,
                    rating=form.cleaned_data["rating"],
                    title=form.cleaned_data.get("title", "").strip(),
                    comment=form.cleaned_data.get("comment", "").strip(),
                    # is_approved default is used; admin can later moderate
                )
        except IntegrityError:
            # Handles race conditions on unique (product, user)
            msg = "You have already reviewed this product."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)
        except Exception as exc:
            logger.error("Error creating review: %s", exc, exc_info=True)
            msg = "Could not submit your review. Please try again."
            if is_ajax:
                return JsonResponse({"success": False, "error": msg}, status=500)
            messages.error(request, msg)
            return redirect("store:product_detail", slug=product.slug)

        success_msg = "Thank you for your review!"
        if is_ajax:
            return JsonResponse({"success": True, "message": success_msg})

        messages.success(request, success_msg)
        return redirect("store:product_detail", slug=product.slug)


def _normalize_image_url(url):
    """Ensure image URL is loadable: add https:// for host-only or protocol-relative URLs. Returns path or absolute URL."""
    if not url or not isinstance(url, str):
        return url
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        base = getattr(settings, "MEDIA_URL", "/media/").rstrip("/")
        if base and url.startswith(base + "/") and "ytimg.com" in url:
            return "https://" + url[len(base) + 1:]
        return url
    return "https://" + url.lstrip("/")


class ProductColorImagesView(View):
    """AJAX: return image URLs for a variant (by variant_id). Used for dynamic gallery on product page."""

    def get(self, request, *args, **kwargs):
        variant_id = request.GET.get("variant_id")
        product_id = request.GET.get("product_id")
        if not variant_id:
            return JsonResponse({"images": []})
        try:
            vid = int(variant_id)
        except (ValueError, TypeError):
            return JsonResponse({"images": []})
        variant = Variant.objects.filter(pk=vid).prefetch_related("images").first()
        if product_id and variant and variant.product_id != int(product_id):
            variant = None
        if not variant:
            return JsonResponse({"images": []})
        images = []
        for img in variant.images.filter(image__isnull=False).exclude(image="").order_by("display_order", "-is_primary", "id"):
            if img.image:
                try:
                    raw_url = img.image.url
                    url = _normalize_image_url(raw_url)
                    if url.startswith("/"):
                        url = request.build_absolute_uri(url)
                    images.append({"url": url, "is_primary": getattr(img, "is_primary", False)})
                except Exception:
                    pass
        return JsonResponse({"images": images})


class ProductVariantResolveView(View):
    """
    AJAX: resolve variant by product_id and selected attribute_value IDs.
    GET/POST: product_id, attribute_value_ids (comma-separated or JSON list).
    Returns: variant_id, price, stock_quantity, in_stock, image_urls, variant_display.
    """
    def _get_ids(self, request):
        product_id = request.GET.get("product_id") or (request.POST.get("product_id") if request.method == "POST" else None)
        ids_raw = request.GET.get("attribute_value_ids") or (request.POST.get("attribute_value_ids") if request.method == "POST" else None)
        if request.body and request.content_type and "application/json" in (request.content_type or ""):
            try:
                data = json.loads(request.body)
                product_id = product_id or data.get("product_id")
                ids_raw = ids_raw or data.get("attribute_value_ids")
                if isinstance(ids_raw, list):
                    return product_id, [int(x) for x in ids_raw if x is not None]
            except (json.JSONDecodeError, TypeError):
                pass
        if ids_raw is None:
            return product_id, []
        if isinstance(ids_raw, str) and "," in ids_raw:
            ids = [int(x.strip()) for x in ids_raw.split(",") if x.strip().isdigit()]
        elif isinstance(ids_raw, list):
            ids = [int(x) for x in ids_raw if x is not None]
        else:
            try:
                ids = [int(ids_raw)]
            except (TypeError, ValueError):
                ids = []
        return product_id, ids

    def get(self, request):
        product_id, attr_value_ids = self._get_ids(request)
        if not product_id:
            return JsonResponse({"success": False, "error": "product_id required"}, status=400)
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Invalid product_id"}, status=400)
        product = Product.objects.filter(pk=product_id, is_active=True).first()
        if not product:
            return JsonResponse({"success": False, "error": "Product not found"}, status=404)
        value_ids = set(attr_value_ids)
        variant = None
        for v in product.variants.filter(is_active=True).prefetch_related("images", "attribute_values"):
            v_ids = set(v.attribute_values.values_list("id", flat=True))
            if v_ids == value_ids:
                variant = v
                break
        if not variant:
            return JsonResponse({"success": False, "error": "Variant not found", "variant": None}, status=404)
        images = list(variant.images.order_by("display_order", "-is_primary", "id"))
        image_urls = []
        for img in images:
            if img.image:
                try:
                    u = img.image.url
                    if u and u.startswith("/"):
                        u = request.build_absolute_uri(u)
                    image_urls.append(u)
                except Exception:
                    pass
        return JsonResponse({
            "success": True,
            "variant": {
                "id": variant.id,
                "price": str(variant.price),
                "stock_quantity": variant.stock_quantity,
                "in_stock": (variant.stock_quantity or 0) > 0,
                "image_urls": image_urls,
                "variant_display": variant.get_attribute_values_display(),
            },
        })

    def post(self, request):
        return self.get(request)


def _serialize_variant_for_json(variant, detail_url=None):
    """Build a dict for JSON APIs where each card represents one Variant (product + variant)."""
    product = getattr(variant, "product", None)
    if not product:
        return {}
    if detail_url is None:
        base = reverse("store:product_detail", args=[product.slug])
        detail_url = f"{base}?variant={variant.id}"
    card_images = []
    for img in getattr(variant, "images", None).all() or []:
        if getattr(img, "image", None):
            try:
                u = img.image.url
                if u:
                    u = _normalize_image_url(u)
                    card_images.append(u)
            except Exception:
                pass
    image_url = card_images[0] if card_images else "/static/images/banner.png"
    has_stock = (variant.stock_quantity or 0) > 0
    is_low_stock = 0 < (variant.stock_quantity or 0) <= 5
    category_name = product.category.name if getattr(product, "category", None) else ""
    avg_rating = getattr(product, "average_rating", None)
    if avg_rating is not None:
        avg_rating = float(avg_rating)
    total_reviews = getattr(product, "total_reviews", None)
    if total_reviews is not None:
        total_reviews = int(total_reviews)
    return {
        "id": product.id,
        "variant_id": variant.id,
        "name": product.name or "",
        "slug": product.slug or "",
        "variant_display": variant.get_attribute_values_display(),
        "price": str(variant.price),
        "url": detail_url,
        "image_url": image_url,
        "card_images": card_images,
        "category_name": category_name or "",
        "has_stock": has_stock,
        "is_low_stock": is_low_stock,
        "average_rating": avg_rating,
        "total_reviews": total_reviews,
        "is_featured": getattr(product, "is_featured", False),
        "is_active": getattr(product, "is_active", True),
        "description": getattr(product, "description", "") or "",
    }


class NewArrivalsView(View):
    """JSON API: latest active variants. ?limit=30 default (capped at 30). One card per product (first variant)."""

    def get(self, request):
        try:
            limit = request.GET.get("limit", "30")
            try:
                limit = min(max(int(limit), 1), 30)
            except (TypeError, ValueError):
                limit = 30
            qs = _active_variant_qs().order_by("-product__created_at", "display_order", "id")
            seen_products = set()
            variants = []
            for v in qs:
                if v.product_id in seen_products:
                    continue
                seen_products.add(v.product_id)
                variants.append(v)
                if len(variants) >= limit:
                    break
            payload = [_serialize_variant_for_json(v) for v in variants]
            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("NewArrivalsView: %s", e)
            return JsonResponse({"products": []})


class TopSellingView(View):
    """JSON API: top selling products from non-cancelled orders. One variant per product."""

    def get(self, request):
        try:
            limit = request.GET.get("limit", "8")
            try:
                limit = min(max(int(limit), 1), 24)
            except (TypeError, ValueError):
                limit = 8
            order_filter = ~Q(order__status=Order.Status.CANCELLED)
            product_ids_with_qty = (
                OrderItem.objects.filter(order_filter)
                .values("product_id")
                .annotate(total_sold=Sum("quantity"))
                .filter(total_sold__gt=0, product__is_active=True)
                .order_by("-total_sold")[:limit * 2]
            )
            ids_ordered = [x["product_id"] for x in product_ids_with_qty]
            if not ids_ordered:
                return JsonResponse({"products": []})
            preserved_order = dict((pk, i) for i, pk in enumerate(ids_ordered))
            qs = _active_variant_qs().filter(product_id__in=ids_ordered)
            seen_products = set()
            variants = []
            for v in sorted(qs, key=lambda x: (preserved_order.get(x.product_id, 999), x.display_order, x.id)):
                if v.product_id in seen_products:
                    continue
                seen_products.add(v.product_id)
                variants.append(v)
                if len(variants) >= limit:
                    break
            payload = [_serialize_variant_for_json(v) for v in variants]
            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("TopSellingView: %s", e)
            return JsonResponse({"products": []})


class RecentlyViewedView(View):
    """JSON API: Variants from session recently_viewed_variant_ids (FIFO, max 20)."""

    def get(self, request):
        try:
            raw_ids = list(request.session.get("recently_viewed_variant_ids", []))
            if not raw_ids:
                return JsonResponse({"products": []})
            seen = set()
            unique_ids = []
            for pk in raw_ids:
                try:
                    pk_int = int(pk)
                except (TypeError, ValueError):
                    continue
                if pk_int in seen:
                    continue
                seen.add(pk_int)
                unique_ids.append(pk_int)
            ids = unique_ids[-RECENTLY_VIEWED_VARIANTS_MAX:]
            if not ids:
                return JsonResponse({"products": []})
            preserved_order = dict((pk, i) for i, pk in enumerate(ids))
            qs = _active_variant_qs().filter(pk__in=ids)
            variants = sorted(list(qs), key=lambda v: preserved_order.get(v.pk, 999))
            payload = [_serialize_variant_for_json(v) for v in variants]
            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("RecentlyViewedView: %s", e)
            return JsonResponse({"products": []})


class YouMayLikeView(View):
    """JSON API: Recommendations - other variants from same categories as recently viewed."""

    def get(self, request):
        try:
            limit = 16
            payload = []
            raw_ids = list(request.session.get("recently_viewed_variant_ids", []))
            viewed_product_ids = set()
            viewed_variant_ids = set()

            if raw_ids:
                seen = set()
                variant_ids = []
                for val in raw_ids:
                    try:
                        vid = int(val)
                    except (TypeError, ValueError):
                        continue
                    if vid in seen:
                        continue
                    seen.add(vid)
                    variant_ids.append(vid)
                viewed_variants = list(_active_variant_qs().filter(pk__in=variant_ids))
                viewed_variant_ids = {v.pk for v in viewed_variants}
                viewed_product_ids = {v.product_id for v in viewed_variants}

                if viewed_product_ids:
                    base_qs = (
                        _active_variant_qs()
                        .filter(product_id__in=viewed_product_ids)
                        .exclude(pk__in=viewed_variant_ids)
                    )
                    candidates = list(base_qs.order_by("product__name", "display_order", "id")[:limit])
                    payload = [_serialize_variant_for_json(v) for v in candidates]

            return JsonResponse({"products": payload})
        except Exception as e:
            logger.exception("YouMayLikeView: %s", e)
            return JsonResponse({"products": []})


class WishlistToggleView(View):
    """POST: toggle variant in wishlist. Body: selected_variant_id. Guest uses session."""

    def post(self, request):
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        variant_id = None
        if request.content_type and "application/json" in request.content_type:
            try:
                data = json.loads(request.body)
                variant_id = data.get("selected_variant_id") or data.get("variant_id")
            except (json.JSONDecodeError, TypeError):
                pass
        if variant_id is None:
            variant_id = request.POST.get("selected_variant_id") or request.POST.get("variant_id")
        try:
            variant_id = int(variant_id) if variant_id else None
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Invalid variant"}, status=400)
        if not variant_id:
            return JsonResponse({"success": False, "error": "Variant required"}, status=400)
        v = (
            Variant.objects.filter(
                pk=variant_id,
                is_active=True,
                product__is_active=True,
            )
            .select_related("product")
            .first()
        )
        if not v:
            return JsonResponse({"success": False, "error": "Variant not found"}, status=404)

        if not request.user.is_authenticated:
            ids = _get_guest_wishlist_ids(request)
            if variant_id in ids:
                ids = [x for x in ids if x != variant_id]
                added = False
            else:
                if len(ids) >= GUEST_WISHLIST_MAX_ITEMS:
                    return JsonResponse({"success": False, "error": "Wishlist is full (max 50 items)."}, status=400)
                ids.append(variant_id)
                added = True
            _set_guest_wishlist_ids(request, ids)
            return JsonResponse({"success": True, "added": added, "count": len(ids)})

        wishlist, created = Wishlist.objects.get_or_create(
            user=request.user, selected_variant=v
        )
        if not created:
            wishlist.delete()
            added = False
        else:
            added = True
        count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse({"success": True, "added": added, "count": count})


class RemoveFromWishlistView(View):
    """POST: remove one item from wishlist by selected_variant_id."""

    def post(self, request):
        variant_id = request.POST.get("selected_variant_id") or request.POST.get("variant_id")
        if request.content_type and "application/json" in request.content_type and request.body:
            try:
                data = json.loads(request.body)
                variant_id = variant_id or data.get("selected_variant_id") or data.get("variant_id")
            except (json.JSONDecodeError, TypeError):
                pass
        try:
            vid = int(variant_id) if variant_id else None
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Invalid variant"}, status=400)
        if not vid:
            return JsonResponse({"success": False, "error": "Variant required"}, status=400)
        if not request.user.is_authenticated:
            ids = _get_guest_wishlist_ids(request)
            if vid not in ids:
                return JsonResponse({"success": True, "removed": False, "count": len(ids)})
            ids = [x for x in ids if x != vid]
            _set_guest_wishlist_ids(request, ids)
            return JsonResponse({"success": True, "removed": True, "count": len(ids)})
        deleted = Wishlist.objects.filter(user=request.user, selected_variant_id=vid).delete()[0]
        count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse({"success": True, "removed": deleted > 0, "count": count})


class WishlistIdsView(View):
    """GET: return wishlist selected_variant IDs for marking hearts. Guest: session variant_ids."""

    def get(self, request):
        if not request.user.is_authenticated:
            variant_ids = _get_guest_wishlist_ids(request)
            return JsonResponse({"variant_ids": variant_ids})
        try:
            variant_ids = list(
                Wishlist.objects.filter(user=request.user)
                .filter(selected_variant__is_active=True, selected_variant__product__is_active=True)
                .values_list("selected_variant_id", flat=True)
            )
            return JsonResponse({"variant_ids": variant_ids})
        except Exception as e:
            logger.exception("WishlistIdsView: %s", e)
            return JsonResponse({"variant_ids": []})


class WishlistPageView(TemplateView):
    """Wishlist page: items by selected_variant. Guest: session-based variant list."""

    template_name = "wishlist.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_authenticated:
            ids = _get_guest_wishlist_ids(self.request)
            if not ids:
                context["wishlist_items"] = []
                context["active_page"] = "wishlist"
                return context
            variants = (
                Variant.objects.filter(
                    pk__in=ids,
                    is_active=True,
                    product__is_active=True,
                )
                .exclude(product__slug="")
                .select_related("product", "product__category")
                .prefetch_related("images")
                .order_by("product__name", "display_order")
            )
            class GuestWishlistItem:
                __slots__ = ("selected_variant",)
                def __init__(self, v):
                    self.selected_variant = v
            context["wishlist_items"] = [GuestWishlistItem(v) for v in variants]
            context["active_page"] = "wishlist"
            return context
        wishlist_items = (
            Wishlist.objects.filter(
                user=self.request.user,
                selected_variant__is_active=True,
                selected_variant__product__is_active=True,
            )
            .exclude(selected_variant__product__slug="")
            .select_related("selected_variant", "selected_variant__product", "selected_variant__product__category")
            .prefetch_related("selected_variant__images")
            .order_by("-created_at")
        )
        context["wishlist_items"] = list(wishlist_items)
        context["active_page"] = "wishlist"
        return context


class CartView(TemplateView):
    template_name = "cart.html"

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            cart = CartService.get_or_create_cart(self.request)
            items = cart.items.select_related(
                "product", "selected_variant",
            ).prefetch_related(
                "selected_variant__images",
            ).all()
            totals = CartService.compute_totals(cart)
            context.update(
                {
                    "cart": cart,
                    "items": items,
                    "totals": totals,
                    "update_form": CartUpdateForm(),
                    "active_page": "cart",
                }
            )
            return context
        except Exception as e:
            logger.error(f"Error in CartView.get_context_data: {str(e)}", exc_info=True)
            context = super().get_context_data(**kwargs)
            context.update({
                "cart": None,
                "items": [],
                "totals": {"subtotal": 0, "gst_total": 0, "shipping": 0, "total": 0},
                "update_form": CartUpdateForm(),
                "active_page": "cart",
            })
            return context


class AddToCartView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        form = CartAddForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid cart data.")
            if is_ajax:
                return JsonResponse({"success": False, "error": "Invalid cart data."}, status=400)
            product_id = request.POST.get("product_id")
            if product_id and Product.objects.filter(pk=product_id).exists():
                product = Product.objects.get(pk=product_id)
                return redirect("store:product_detail", slug=product.slug)
            return redirect("store:cart")
        data = form.cleaned_data
        product = get_object_or_404(Product, pk=data["product_id"])
        sellable = None

        if data.get("variant_id"):
            variant = Variant.objects.filter(
                product=product,
                pk=data["variant_id"],
                is_active=True,
                stock_quantity__gt=0,
            ).select_related("product").first()
            if variant:
                sellable = variant
        if not sellable:
            messages.error(request, "Please select a variant (e.g. model/color) or selected variant is unavailable.")
            if is_ajax:
                return JsonResponse({"success": False, "error": "Please select a variant or selected variant is unavailable."}, status=400)
            return redirect("store:product_detail", slug=product.slug)

        cart = CartService.get_or_create_cart(request)
        try:
            CartService.add_item(cart, sellable, data["quantity"])
        except StockError as exc:
            messages.error(request, str(exc))
            if is_ajax:
                return JsonResponse({"success": False, "error": str(exc)}, status=400)
        else:
            if is_ajax:
                cart_count = sum(item.quantity for item in cart.items.all())
                return JsonResponse({"success": True, "cart_count": cart_count})
        action = request.POST.get("action", "add")
        if action == "buy":
            return redirect("store:checkout")
        # Add ?added=1 to cart redirect for notification
        url = reverse("store:cart") + "?added=1"
        return redirect(url)


class BuyNowView(View):
    """
    Buy only the selected product: clear cart, add this item, redirect to checkout.
    Used from product detail page so checkout shows only this product.
    """
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        form = CartAddForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please select a variant and quantity.")
            product_id = request.POST.get("product_id")
            if product_id and Product.objects.filter(pk=product_id).exists():
                product = Product.objects.get(pk=product_id)
                return redirect("store:product_detail", slug=product.slug)
            return redirect("store:cart")

        data = form.cleaned_data
        product = get_object_or_404(Product, pk=data["product_id"])
        variant = None
        if data.get("variant_id"):
            variant = Variant.objects.filter(
                product=product,
                pk=data["variant_id"],
                is_active=True,
                stock_quantity__gt=0,
            ).select_related("product").first()

        if not variant:
            messages.error(request, "Please select a variant or the selected variant is unavailable.")
            return redirect("store:product_detail", slug=product.slug)

        cart = CartService.get_or_create_cart(request)
        try:
            cart.items.all().delete()
            CartService.add_item(cart, variant, data["quantity"])
        except StockError as exc:
            messages.error(request, str(exc))
            return redirect("store:product_detail", slug=product.slug)

        return redirect("store:checkout")


class UpdateCartItemView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        form = CartUpdateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid update.")
            return redirect("store:cart")
        cart = CartService.get_or_create_cart(request)
        item = get_object_or_404(CartItem, pk=form.cleaned_data["item_id"], cart=cart)
        try:
            CartService.update_item(item, form.cleaned_data["quantity"])
        except StockError as exc:
            messages.error(request, str(exc))
        return redirect("store:cart")


class RemoveCartItemView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and not next_url.startswith("/"):
            next_url = None
        try:
            cart = CartService.get_or_create_cart(request)
            item = get_object_or_404(CartItem, pk=kwargs.get("item_id"), cart=cart)
            item.delete()
            messages.success(request, "Item removed.")
        except Exception as e:
            logger.error("Error in RemoveCartItemView: %s", e, exc_info=True)
            messages.error(request, "Failed to remove item from cart.")
        if next_url:
            return redirect(next_url)
        return redirect("store:cart")


class CheckoutView(TemplateView):
    template_name = "checkout.html"

    def dispatch(self, request, *args, **kwargs):
        cart = CartService.get_or_create_cart(request)
        if not cart.items.exists():
            messages.info(request, "Your cart is empty.")
            return redirect("store:cart")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            cart = CartService.get_or_create_cart(self.request)
            totals = CartService.compute_totals(cart)
            user = self.request.user if self.request.user.is_authenticated else None

            addresses = []
            default_address = None
            initial = {}
            if user:
                from .models import Address
                addresses = list(
                    Address.objects.filter(user=user, is_snapshot=False).order_by("-is_default", "-created_at")
                )
                default_address = next((a for a in addresses if a.is_default), addresses[0] if addresses else None)
                payment_method = self.request.GET.get("payment")
                if payment_method in ("cod", "razorpay"):
                    initial["payment"] = payment_method
                if default_address:
                    initial["selected_address"] = default_address.id
            else:
                payment_method = self.request.GET.get("payment")
                if payment_method in ("cod", "razorpay"):
                    initial["payment"] = payment_method

            context.update(
                {
                    "cart": cart,
                    "items": cart.items.select_related(
                        "product", "selected_variant",
                    ).prefetch_related(
                        "selected_variant__images",
                    ),
                    "totals": totals,
                    "form": CheckoutForm(initial=initial, user=user),
                    "addresses": addresses,
                    "default_address": default_address,
                    "is_guest_checkout": user is None,
                    "active_page": "checkout",
                }
            )
            return context
        except Exception as e:
            logger.error(f"Error in CheckoutView.get_context_data: {str(e)}", exc_info=True)
            user = self.request.user if self.request.user.is_authenticated else None
            context = super().get_context_data(**kwargs)
            context.update({
                "cart": None,
                "items": [],
                "totals": {"subtotal": 0, "gst_total": 0, "shipping": 0, "total": 0},
                "form": CheckoutForm(user=user),
                "addresses": [],
                "default_address": None,
                "is_guest_checkout": user is None,
                "active_page": "checkout",
            })
            return context


class OrderCreateView(FormView):
    form_class = CheckoutForm
    template_name = "checkout.html"

    def dispatch(self, request, *args, **kwargs):
        cart = CartService.get_or_create_cart(request)
        if not cart.items.exists():
            messages.info(request, "Your cart is empty.")
            return redirect("store:cart")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user if self.request.user.is_authenticated else None
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = CartService.get_or_create_cart(self.request)
        totals = CartService.compute_totals(cart)
        user = self.request.user if self.request.user.is_authenticated else None
        addresses = []
        default_address = None
        if user:
            from .models import Address
            addresses = list(
                Address.objects.filter(user=user, is_snapshot=False).order_by("-is_default", "-created_at")
            )
            default_address = next((a for a in addresses if a.is_default), addresses[0] if addresses else None)
        context.update({
            "cart": cart,
            "items": cart.items.select_related(
                "product", "selected_variant",
            ).prefetch_related(
                "selected_variant__images",
            ),
            "totals": totals,
            "addresses": addresses,
            "default_address": default_address,
            "is_guest_checkout": user is None,
            "active_page": "checkout",
        })
        return context

    def form_valid(self, form):
        """Handle COD only. Razorpay is handled via JS and CreateRazorpayOrderView."""
        cart = CartService.get_or_create_cart(self.request)
        payment_method = form.cleaned_data.get("payment")
        order_user = self.request.user if self.request.user.is_authenticated else None

        if payment_method == "razorpay":
            messages.info(self.request, "Please use the Pay & Place Order button for online payment.")
            return redirect("store:checkout")

        try:
            order = OrderService.create_order(cart, form.cleaned_data, user=order_user, clear_cart=True)
        except (CartError, StockError) as exc:
            messages.error(self.request, str(exc))
            return redirect("store:checkout")
        self.request.session["last_order_number"] = order.order_number
        return redirect("store:order_success", order_number=order.order_number)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class CreateRazorpayOrderView(View):
    """
    Create order (status=PLACED, payment=PENDING) and Razorpay order in one flow.
    Amount is always computed server-side from cart. No redirect to payment page.
    """
    def post(self, request, *args, **kwargs):
        cart = CartService.get_or_create_cart(request)
        if not cart.items.exists():
            return JsonResponse({"status": "error", "message": "Your cart is empty."}, status=400)

        user = request.user if request.user.is_authenticated else None
        form = CheckoutForm(request.POST, user=user)
        if not form.is_valid():
            msg = "Please check your details."
            for field in ("__all__", "payment", "full_name", "phone", "address_line", "city", "state", "pincode", "email"):
                errs = form.errors.get(field)
                if errs:
                    msg = errs[0] if isinstance(errs[0], str) else str(errs[0])
                    break
            return JsonResponse({"status": "error", "message": msg}, status=400)

        cleaned = form.cleaned_data
        if cleaned.get("payment") != "razorpay":
            return JsonResponse({"status": "error", "message": "Invalid payment method."}, status=400)

        try:
            with transaction.atomic():
                items = list(
                    cart.items.select_related("selected_variant", "product")
                    .select_for_update(of=("self",))
                    .all()
                )
                if not items:
                    return JsonResponse({"status": "error", "message": "Cart is empty."}, status=400)
                for item in items:
                    v = item.selected_variant
                    if not v:
                        return JsonResponse({"status": "error", "message": "Invalid cart item."}, status=400)
                    if (v.stock_quantity or 0) < item.quantity:
                        return JsonResponse(
                            {"status": "error", "message": f"{item.product.name} is out of stock."},
                            status=400,
                        )

                order = OrderService.create_order(cart, cleaned, user=user, clear_cart=False)
                order.status = Order.Status.PLACED
                order.save(update_fields=["status"])

                request.session["pending_checkout_data"] = cleaned
                request.session["last_order_number"] = order.order_number

                payment = order.payment
                client = razorpay.Client(auth=(settings.RZP_CLIENT_ID, settings.RZP_CLIENT_SECRET))
                totals = CartService.compute_totals(cart)
                amount_paise = int(totals.total * 100)
                razorpay_order = client.order.create({
                    "amount": amount_paise,
                    "currency": "INR",
                    "payment_capture": 1,
                })
                payment.razorpay_order_id = razorpay_order["id"]
                payment.save(update_fields=["razorpay_order_id"])

            customer_email = (order.address.email or "") if order.address else ""
            if user and not customer_email:
                customer_email = getattr(user, "email", "") or ""

            return JsonResponse({
                "status": "success",
                "razorpay_order_id": razorpay_order["id"],
                "razorpay_key_id": settings.RZP_CLIENT_ID,
                "amount": amount_paise,
                "order_number": order.order_number,
                "customer_name": order.address.full_name if order.address else "",
                "customer_email": customer_email,
                "customer_phone": order.address.phone if order.address else "",
                "success_url": reverse("store:order_success", kwargs={"order_number": order.order_number}),
            })
        except (CartError, StockError) as exc:
            return JsonResponse({"status": "error", "message": str(exc)}, status=400)
        except Exception as e:
            logger.exception("CreateRazorpayOrderView error: %s", e)
            return JsonResponse({"status": "error", "message": "Unable to create order. Please try again."}, status=500)


class OrderSuccessView(DetailView):
    template_name = "success.html"
    context_object_name = "order"
    slug_url_kwarg = "order_number"
    slug_field = "order_number"

    def get_queryset(self):
        return Order.objects.select_related("address", "payment", "shipment").prefetch_related("items")

    def dispatch(self, request, *args, **kwargs):
        try:
            order_number = kwargs.get("order_number")
            order = get_object_or_404(Order, order_number=order_number)
            if request.user.is_authenticated:
                if order.user and order.user != request.user:
                    return HttpResponseForbidden()
            else:
                if request.session.get("last_order_number") != order_number:
                    return HttpResponseForbidden()
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            logger.warning(f"Order not found: {order_number}")
            raise
        except Exception as e:
            logger.error(f"Error in OrderSuccessView.dispatch: {str(e)}", exc_info=True)
            messages.error(request, "Failed to retrieve order details.")
            return redirect("store:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "orders"
        return context


class OrderDetailPageView(LoginRequiredMixin, DetailView):
    """
    Dedicated order detail page for logged-in users.
    Uses the same rich layout as the checkout success page,
    but without relying on the last_order_number session guard.
    """

    template_name = "order_detail.html"
    context_object_name = "order"
    slug_url_kwarg = "order_number"
    slug_field = "order_number"

    def get_queryset(self):
        # Restrict orders to the logged-in user
        return (
            Order.objects.select_related("address", "payment", "shipment")
            .prefetch_related("items")
            .filter(user=self.request.user)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "orders"
        return context


class OrderHistoryView(LoginRequiredMixin, ListView):
    template_name = "orders.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        try:
            return (
                Order.objects.filter(user=self.request.user)
                .select_related("address")
                .prefetch_related("items")
            )
        except Exception as e:
            logger.error(f"Error in OrderHistoryView.get_queryset: {str(e)}", exc_info=True)
            return Order.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "orders"
        return context


class ContactView(FormView):
    template_name = "contact.html"
    form_class = ContactForm
    success_url = reverse_lazy("store:contact")

    def form_valid(self, form):
        try:
            form.save()
            messages.success(self.request, "Thanks for reaching out! We will respond soon.")
        except Exception as e:
            logger.error(f"Error in ContactView.form_valid: {str(e)}", exc_info=True)
            messages.error(self.request, "Failed to save your message. Please try again.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_page"] = "contact"
        return context


class StaticPageView(TemplateView):
    template_name = "about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.extra_context and "active_page" in self.extra_context:
            context["active_page"] = self.extra_context["active_page"]
        return context


class NewsletterSubscribeView(FormView):
    form_class = NewsletterForm
    success_url = reverse_lazy("store:home")

    def get_success_url(self):
        return self.request.META.get("HTTP_REFERER", str(self.success_url))

    def form_valid(self, form):
        try:
            email = form.cleaned_data["email"].lower()
            subscription, created = form._meta.model.objects.get_or_create(email=email)
            if not created and not subscription.is_active:
                subscription.is_active = True
                subscription.save(update_fields=["is_active"])
            messages.success(self.request, "Thanks for subscribing!")
        except Exception as e:
            logger.error(f"Error in NewsletterSubscribeView.form_valid: {str(e)}", exc_info=True)
            messages.error(self.request, "Failed to subscribe. Please try again.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please enter a valid email.")
        return redirect(self.get_success_url())


class RazorpayPaymentVerifyView(View):
    """Verify Razorpay payment signature. Guest-safe; idempotent if already PAID."""

    def post(self, request, *args, **kwargs):
        try:
            # Accept both JSON (AJAX) and standard form POSTs (e.g. Razorpay callback_url)
            razorpay_order_id = request.POST.get("razorpay_order_id")
            razorpay_payment_id = request.POST.get("razorpay_payment_id")
            razorpay_signature = request.POST.get("razorpay_signature")

            if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
                try:
                    data = json.loads(request.body or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    data = {}
                razorpay_order_id = razorpay_order_id or data.get("razorpay_order_id")
                razorpay_payment_id = razorpay_payment_id or data.get("razorpay_payment_id")
                razorpay_signature = razorpay_signature or data.get("razorpay_signature")

            if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Missing payment parameters.",
                        "redirect": "/cart/",
                    },
                    status=400,
                )

            logger.info("Payment verification attempt - Order: %s, Payment: %s", razorpay_order_id, razorpay_payment_id)

            payment = Payment.objects.select_related('order').get(razorpay_order_id=razorpay_order_id)

            # Idempotent: already paid (e.g. double callback)
            if payment.status == Payment.Status.PAID:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment already verified',
                    'order_number': payment.order.order_number,
                    'redirect': reverse('store:order_success', kwargs={'order_number': payment.order.order_number}),
                })

            signature_data = f"{razorpay_order_id}|{razorpay_payment_id}"
            signature_check = hmac.new(
                settings.RZP_CLIENT_SECRET.encode(),
                signature_data.encode(),
                hashlib.sha256
            ).hexdigest()

            if signature_check == razorpay_signature:
                payment.razorpay_payment_id = razorpay_payment_id
                payment.razorpay_signature = razorpay_signature
                payment.status = Payment.Status.PAID
                payment.processed_at = timezone.now()
                payment.save(update_fields=['status', 'processed_at', 'razorpay_payment_id', 'razorpay_signature'])

                order = payment.order
                order.status = Order.Status.CONFIRMED
                order.save(update_fields=["status"])
                for item in order.items.select_related("product", "selected_variant").all():
                    if item.selected_variant_id:
                        Variant.objects.filter(pk=item.selected_variant_id).update(
                            stock_quantity=F("stock_quantity") - item.quantity
                        )

                cart = CartService.get_or_create_cart(request)
                if cart.items.exists():
                    cart.status = Cart.Status.ORDERED
                    cart.save(update_fields=["status"])
                    cart.items.all().delete()

                if "pending_checkout_data" in request.session:
                    del request.session["pending_checkout_data"]

                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment verified successfully',
                    'order_number': payment.order.order_number,
                    'redirect': reverse('store:order_success', kwargs={'order_number': payment.order.order_number}),
                })
            else:
                # Payment signature verification failed
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=['status'])
                
                # Delete the order since payment failed (no stock was reduced)
                order = payment.order
                order_number = order.order_number
                order.delete()  # This will cascade delete the payment and order items
                
                # Clear pending checkout data from session
                if "pending_checkout_data" in request.session:
                    del request.session["pending_checkout_data"]
                
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment verification failed. Please try again.',
                    'redirect': '/cart/'
                }, status=400)
        except Payment.DoesNotExist:
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'error',
                'message': 'Payment record not found',
                'redirect': '/cart/'
            }, status=404)
        except Exception as e:
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'error',
                'message': f'Payment verification error: {str(e)}',
                'redirect': '/cart/'
            }, status=500)


class RazorpayPaymentCancelView(View):
    """Handle Razorpay payment cancellation. Guest: authorized by session last_order_number."""

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            order_number = data.get('order_number')
            order = Order.objects.select_related('user', 'address').get(order_number=order_number)
            if request.user.is_authenticated:
                if order.user_id != request.user.id:
                    return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            else:
                if request.session.get("last_order_number") != order_number:
                    return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            
            # Get payment record
            try:
                payment = order.payment
            except Payment.DoesNotExist:
                payment = None
            
            # Delete the order (cascade deletes payment and items)
            order.delete()
            
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payment cancelled. Your order has been cancelled.',
                'redirect': '/cart/'
            })
        except Order.DoesNotExist:
            logger.warning("Order not found for cancellation: %s", order_number)
            
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'success',
                'message': 'Returning to cart...',
                'redirect': '/cart/'
            })
        except Exception as e:
            # Clear pending checkout data from session
            if "pending_checkout_data" in request.session:
                del request.session["pending_checkout_data"]
            
            return JsonResponse({
                'status': 'success',
                'message': 'Returning to cart...',
                'redirect': '/cart/'
            })