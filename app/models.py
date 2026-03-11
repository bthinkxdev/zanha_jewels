from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
import hashlib
import secrets
import string
import random

import logging

logger = logging.getLogger(__name__)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    is_active = models.BooleanField(default=True, db_index=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            
            # Handle duplicate slugs by appending 4-character random string
            while Category.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                self.slug = f"{base_slug}-{random_suffix}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def available(self):
        from django.db.models import Q
        return (
            self.active()
            .filter(
                Q(variants__is_active=True, variants__stock_quantity__gt=0)
                | Q(variants__isnull=True, base_stock__gt=0)
            )
            .distinct()
        )


class Product(TimeStampedModel):
    """
    Universal product. No variant fields; pricing/stock/images live on Variant/VariantImage.
    Attributes (e.g. Color, Storage) are defined via ProductAttribute / ProductAttributeValue.
    """
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=120, blank=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_bestseller = models.BooleanField(default=False, db_index=True)
    is_deal_of_day = models.BooleanField(default=False, db_index=True)
    deal_of_day_start = models.DateField(blank=True, null=True, db_index=True)
    deal_of_day_end = models.DateField(blank=True, null=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        help_text="Average star rating from verified reviews (1-5).",
    )
    total_reviews = models.PositiveIntegerField(
        default=0,
        help_text="Total number of approved, non-deleted reviews.",
    )
    # GST (India): optional per product
    is_gst_applicable = models.BooleanField(default=False, db_index=True)
    gst_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="GST %% (0-28). Required when is_gst_applicable is True.",
    )
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    # Simple product base fields (used only when the product has no variants)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_stock = models.PositiveIntegerField(null=True, blank=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["is_active", "is_bestseller"]),
            models.Index(fields=["is_active", "is_deal_of_day"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_active", "brand"]),
        ]

    def clean(self):
        super().clean()
        if self.is_gst_applicable:
            if self.gst_percentage is None:
                raise ValidationError({"gst_percentage": "GST %% is required when GST is applicable."})
            try:
                pct = Decimal(str(self.gst_percentage))
                if pct < 0 or pct > 28:
                    raise ValidationError(
                        {"gst_percentage": "GST %% must be between 0 and 28."}
                    )
            except (TypeError, ValueError):
                raise ValidationError({"gst_percentage": "Enter a valid GST percentage."})
        else:
            if self.gst_percentage is not None:
                raise ValidationError(
                    {"gst_percentage": "Clear GST %% when GST is not applicable."}
                )

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                self.slug = f"{base_slug}-{random_suffix}"
        super().save(*args, **kwargs)

    def _normalize_card_image_url(self, url):
        if not url or not isinstance(url, str):
            return url
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            base = getattr(settings, "MEDIA_URL", "/media/").rstrip("/")
            if base and "/media/" in url and "ytimg.com" in url and url.startswith(base + "/"):
                return "https://" + url[len(base) + 1:]
            return url
        return "https://" + url.lstrip("/")

    def has_any_sellable_stock(self):
        if getattr(self, "_has_sellable_stock", None) is not None:
            return self._has_sellable_stock
        # When variants exist, they are the source of truth
        if self.variants.exists():
            for v in self.variants.all():
                if getattr(v, "is_active", True) and (getattr(v, "stock_quantity", 0) or 0) > 0:
                    self._has_sellable_stock = True
                    return True
            self._has_sellable_stock = False
            return False
        # Simple product: fall back to base_stock
        stock = getattr(self, "base_stock", None)
        self._has_sellable_stock = bool(stock and stock > 0)
        return self._has_sellable_stock

    # --- Simple vs variant helpers ---
    def has_variants(self):
        return self.variants.exists()

    def is_simple_product(self):
        return not self.has_variants()

    def get_price(self):
        """
        Returns the display price for this product.
        When variants exist, uses the lowest active variant price.
        Otherwise falls back to base_price.
        """
        if self.has_variants():
            v = (
                self.variants.filter(is_active=True)
                .order_by("price")
                .only("price")
                .first()
            )
            return v.price if v else None
        return self.base_price

    def get_stock(self):
        """
        Returns total sellable stock for this product.
        When variants exist, sums active variant stock.
        Otherwise falls back to base_stock.
        """
        if self.has_variants():
            return sum(
                (v.stock_quantity or 0)
                for v in self.variants.filter(is_active=True).only("stock_quantity")
            )
        return self.base_stock or 0

    def get_card_image_urls(self, limit=20):
        urls = []
        seen = set()
        try:
            # If variants exist, variant images are the source of truth
            if self.variants.exists():
                for v in self.variants.filter(is_active=True).order_by("display_order", "id"):
                    if len(urls) >= limit:
                        break
                    for img in v.images.filter(image__isnull=False).exclude(image="").order_by("-is_primary", "display_order", "id")[:1]:
                        if img.image:
                            url = img.image.url
                            if url:
                                url = self._normalize_card_image_url(url)
                            if url and url not in seen:
                                seen.add(url)
                                urls.append(url)
                                break
            else:
                # Simple product: use ProductImage records
                for img in self.images.filter(image__isnull=False).exclude(image="").order_by("-is_primary", "display_order", "id")[:limit]:
                    if img.image:
                        url = img.image.url
                        if url:
                            url = self._normalize_card_image_url(url)
                        if url and url not in seen:
                            seen.add(url)
                            urls.append(url)
        except Exception:
            pass
        # Hard limit to 3 images for simple products at call site via limit param;
        # fallback to provided limit for other usage.
        return urls[:limit] if urls else []

    def __str__(self):
        return self.name


class ProductAttribute(TimeStampedModel):
    """Attribute name per product (e.g. Color, Storage, Compatible Model)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes")
    name = models.CharField(max_length=120)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "name"], name="unique_product_attribute_name"),
        ]
        indexes = [
            models.Index(fields=["product", "display_order"]),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.name}"


class ProductAttributeValue(TimeStampedModel):
    """Value for an attribute (e.g. Black, 128GB, iPhone 17 Pro Max)."""
    attribute = models.ForeignKey(
        ProductAttribute, on_delete=models.CASCADE, related_name="values"
    )
    value = models.CharField(max_length=200)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "value", "id"]
        constraints = [
            models.UniqueConstraint(fields=["attribute", "value"], name="unique_attribute_value"),
        ]
        indexes = [
            models.Index(fields=["attribute", "display_order"]),
        ]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class Variant(TimeStampedModel):
    """
    Single sellable variant: product + set of attribute values. Price, stock, SKU, images per variant.
    Unique combination of attribute values per product (enforced in clean/save).
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute_values = models.ManyToManyField(
        ProductAttributeValue,
        related_name="variants",
        through="VariantAttributeValue",
        blank=True,
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock_quantity = models.PositiveIntegerField(default=0)
    # Physical dimensions for shipping (weight in kg, dimensions in cm)
    weight = models.DecimalField(max_digits=6, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    length = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    breadth = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    height = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    sku = models.CharField(max_length=64, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0),
                name="variant_stock_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="variant_price_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "is_active", "stock_quantity"]),
        ]

    def get_attribute_values_display(self):
        """Human-readable string of attribute values (e.g. 'Black / 128GB')."""
        values = list(
            self.attribute_values.select_related("attribute").order_by("attribute__display_order", "display_order")
        )
        return " / ".join(av.value for av in values) if values else ""

    def __str__(self):
        display = self.get_attribute_values_display()
        return f"{self.product.name} — {display}" if display else f"{self.product.name} (variant #{self.pk})"


class VariantAttributeValue(TimeStampedModel):
    """Through model: which attribute values belong to a variant (one value per attribute per variant)."""
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="variant_attr_values")
    attribute_value = models.ForeignKey(
        ProductAttributeValue, on_delete=models.CASCADE, related_name="variant_attr_values"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "attribute_value"],
                name="unique_variant_attribute_value",
            ),
        ]


class VariantImage(TimeStampedModel):
    """Image for a specific variant."""
    variant = models.ForeignKey(
        Variant, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/variant_images/")
    is_primary = models.BooleanField(default=False, db_index=True)
    alt_text = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "-is_primary", "id"]
        indexes = [
            models.Index(fields=["variant", "is_primary"]),
            models.Index(fields=["variant", "display_order"]),
        ]

    def __str__(self):
        return f"{self.variant} image"


class ProductImage(TimeStampedModel):
    """
    Base images for simple products (products without variants).
    When variants exist for a product, VariantImage becomes the source of truth
    and ProductImage records, if any, are ignored on the storefront.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/base_images/")
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "-is_primary", "id"]
        indexes = [
            models.Index(fields=["product", "display_order"]),
        ]

    def __str__(self):
        return f"{self.product} base image"


class Cart(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ORDERED = "ordered", "Ordered"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True, related_name="carts")
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["session_key", "status"]),
        ]

    def __str__(self):
        return f"Cart {self.pk} ({self.status})"

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.select_related("product"))

    def _get_gst_aggregates(self):
        """Returns (taxable_total, non_taxable_total, gst_total) from items. One pass."""
        from decimal import Decimal
        taxable = Decimal("0")
        non_taxable = Decimal("0")
        gst_total = Decimal("0")
        for item in self.items.select_related("product"):
            line = item.line_total
            if getattr(item.product, "is_gst_applicable", False) and getattr(item.product, "gst_percentage", None) is not None:
                taxable += line
                pct = item.product.gst_percentage
                gst_total += line * (pct / Decimal("100"))
            else:
                non_taxable += line
        return taxable, non_taxable, gst_total

    @property
    def taxable_total(self):
        return self._get_gst_aggregates()[0]

    @property
    def non_taxable_total(self):
        return self._get_gst_aggregates()[1]

    @property
    def gst_total(self):
        return self._get_gst_aggregates()[2]

    @property
    def grand_total(self):
        return self.subtotal + self.gst_total


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="cart_items")
    selected_variant = models.ForeignKey(
        Variant, on_delete=models.PROTECT, related_name="cart_items", null=True, blank=True
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "selected_variant"],
                name="unique_cart_selected_variant",
                condition=models.Q(selected_variant__isnull=False),
            ),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cartitem_qty_positive"),
        ]
        indexes = [
            models.Index(fields=["cart", "product"]),
        ]

    @property
    def variant_display(self):
        if self.selected_variant_id and self.selected_variant:
            return self.selected_variant.get_attribute_values_display()
        return ""

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def get_display_image_url(self):
        """
        Return the first image URL for this cart item (variant image or product base image for simple products).
        Returns None if no image is available.
        """
        if self.selected_variant_id:
            for img in self.selected_variant.images.filter(
                image__isnull=False
            ).exclude(image="").order_by("-is_primary", "display_order", "id")[:1]:
                try:
                    if img.image:
                        return img.image.url
                except Exception:
                    pass
            return None
        if self.product_id:
            urls = self.product.get_card_image_urls(limit=1)
            return urls[0] if urls else None
        return None

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Address(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="addresses")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address_line = models.TextField()
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    pincode = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False, db_index=True)
    is_snapshot = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_default"]),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.city}"


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PLACED = "placed", "Placed"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="orders")
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLACED, db_index=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    shipping = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    gst_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    igst = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name="orders")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    selected_variant = models.ForeignKey(
        Variant, on_delete=models.PROTECT, related_name="order_items", null=True, blank=True
    )
    product_name = models.CharField(max_length=200)
    variant_snapshot = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    # Invoice / GST snapshot (for GST products only)
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    gst_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    taxable_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Line taxable value (unit_price * qty) for GST lines.",
    )
    gst_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="GST amount for this line.",
    )

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.order.order_number} - {self.product_name}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        WHATSAPP = "whatsapp", "WhatsApp Order"
        RAZORPAY = "razorpay", "Online Payment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.COD, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    processed_at = models.DateTimeField(blank=True, null=True)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    def mark_paid(self):
        self.status = self.Status.PAID
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at"])


class Shipment(TimeStampedModel):
    """
    Outbound shipment metadata for an order (Shiprocket integration).
    Kept separate from Order for clearer lifecycle and error handling.
    """

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment")
    shiprocket_order_id = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_shipment_id = models.CharField(max_length=100, blank=True, null=True)
    awb_code = models.CharField(max_length=100, blank=True, null=True)
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    label_url = models.URLField(blank=True, null=True)
    current_status = models.CharField(max_length=100, blank=True, null=True)
    tracking_data = models.JSONField(blank=True, null=True, default=dict)
    is_cancelled = models.BooleanField(default=False, db_index=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    error_log = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["awb_code"]),
            models.Index(fields=["shiprocket_order_id"]),
            models.Index(fields=["shiprocket_shipment_id"]),
            models.Index(fields=["is_cancelled"]),
        ]

    def __str__(self):
        return f"Shipment for {self.order.order_number}"


class ContactMessage(TimeStampedModel):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"


class NewsletterSubscription(TimeStampedModel):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return self.email


class Wishlist(TimeStampedModel):
    """User wishlist: one entry per selected variant."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    selected_variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "selected_variant"],
                name="unique_user_selected_variant_wishlist",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.selected_variant}"


class UserProfile(TimeStampedModel):
    """Extended user profile for additional user information"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Profile: {self.user.email}"


class Banner(TimeStampedModel):
    """Home page banner for carousel. Maximum number of active banners enforced at save."""
    MAX_ACTIVE = 5

    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to="banners/")
    redirect_url = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "created_at"]
        indexes = [
            models.Index(fields=["is_active", "display_order"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        active = (
            Banner.objects.filter(is_active=True)
            .order_by("display_order", "created_at")
        )
        if active.count() > self.MAX_ACTIVE:
            to_deactivate = active[self.MAX_ACTIVE:]
            Banner.objects.filter(pk__in=to_deactivate.values_list("pk", flat=True)).update(
                is_active=False
            )

    def __str__(self):
        return self.title or f"Banner #{self.pk}"


class OTPRequest(TimeStampedModel):
    """Store OTP requests for email-based authentication"""
    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=64)  # SHA256 hash of OTP
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    attempts = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'is_used', 'expires_at']),
            models.Index(fields=['created_at', 'email']),
        ]
    
    def __str__(self):
        return f"OTP for {self.email} - {'Used' if self.is_used else 'Active'}"
    
    @staticmethod
    def hash_otp(otp):
        """Hash OTP using SHA256"""
        return hashlib.sha256(str(otp).encode()).hexdigest()
    
    def verify_otp(self, otp):
        """Verify provided OTP against stored hash"""
        return self.otp_hash == self.hash_otp(otp)
    
    def is_valid(self):
        """Check if OTP is still valid (not expired, not used)"""
        return not self.is_used and timezone.now() < self.expires_at
    
    @classmethod
    def generate_otp(cls):
        """Generate a secure 4-digit OTP"""
        return str(secrets.randbelow(10000)).zfill(4)


class Review(TimeStampedModel):
    """
    Product review from a verified buyer.

    Business rules:
    - Only logged-in users can create reviews (enforced in views).
    - User must have at least one delivered order for the product.
    - One review per (product, user).
    - Rating is 1–5 stars.
    - Reviews can be moderated via is_approved.
    - Reviews are soft-deleted via is_deleted flag.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviews",
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        related_name="reviews",
        null=True,
        blank=True,
        help_text="The delivered order that verified this review.",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Only approved reviews are shown on the storefront.",
    )
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft delete flag; deleted reviews are hidden but kept for history.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                name="unique_product_user_review",
            ),
            # Use `condition=` for compatibility with the project's Django version
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
        ]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["is_approved"]),
            models.Index(fields=["product", "is_approved"]),
        ]

    def __str__(self):
        uname = getattr(self.user, "username", "Anonymous")
        return f"Review for {self.product} by {uname} ({self.rating}★)"


def _recompute_product_rating(product_id: int):
    """
    Efficiently recompute average rating and total reviews for a single product.
    Only considers approved, non-deleted reviews.
    """
    if not product_id:
        return
    qs = Review.objects.filter(
        product_id=product_id,
        is_approved=True,
        is_deleted=False,
    )
    agg = qs.aggregate(
        avg=Avg("rating"),
        cnt=Count("id"),
    )
    avg = agg["avg"] or 0
    cnt = agg["cnt"] or 0
    # Update only the two fields for this product
    Product.objects.filter(pk=product_id).update(
        average_rating=avg,
        total_reviews=cnt,
    )


@receiver(post_save, sender=Review)
def review_post_save(sender, instance: Review, **kwargs):
    """
    Recompute product aggregates whenever a review is created or updated
    (e.g. approval status changed, soft-deleted).
    """
    _recompute_product_rating(instance.product_id)


@receiver(post_delete, sender=Review)
def review_post_delete(sender, instance: Review, **kwargs):
    """
    Support physical deletions as well (e.g. if ever used).
    """
    _recompute_product_rating(instance.product_id)


@receiver(post_save, sender=Order)
def auto_create_shipment_on_confirmed(sender, instance: Order, created: bool, update_fields=None, **kwargs):
    """
    When an order is marked CONFIRMED, automatically create a Shipment and
    trigger Shiprocket fulfillment if a shipment does not already exist.

    This behavior is skipped entirely when DELIVERY_INTEGRATED is disabled.
    """
    try:
        from .delivery_utils import delivery_enabled

        if not delivery_enabled():
            return

        if instance.status != Order.Status.CONFIRMED:
            return
        # Only react when status was part of the save or on generic saves
        if not created and update_fields is not None and "status" not in update_fields:
            return

        if hasattr(instance, "shipment"):
            # Shipment already exists; do not create another
            return

        from .services.shiprocket_service import create_shipment_for_order, ShiprocketAPIError

        shipment = Shipment.objects.create(order=instance, current_status="pending_creation")
        try:
            create_shipment_for_order(instance, shipment)
        except ShiprocketAPIError as exc:
            shipment.error_log = str(exc)
            shipment.current_status = "error"
            shipment.save(update_fields=["error_log", "current_status", "updated_at"])
            logger.error("Shiprocket shipment creation failed for order %s: %s", instance.order_number, exc, exc_info=True)
        except Exception as exc:
            shipment.error_log = str(exc)
            shipment.current_status = "error"
            shipment.save(update_fields=["error_log", "current_status", "updated_at"])
            logger.error("Unexpected error during shipment creation for order %s: %s", instance.order_number, exc, exc_info=True)
    except Exception as outer_exc:
        logger.error("auto_create_shipment_on_confirmed failed for order %s: %s", getattr(instance, "order_number", None), outer_exc, exc_info=True)
