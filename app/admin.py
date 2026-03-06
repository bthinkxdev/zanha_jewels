from django.contrib import admin

from .models import (
    Address,
    Banner,
    Cart,
    CartItem,
    Category,
    ContactMessage,
    NewsletterSubscription,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    Review,
    Variant,
    VariantAttributeValue,
    VariantImage,
    Wishlist,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "is_featured", "is_bestseller", "is_active")
    list_filter = ("category", "is_featured", "is_bestseller", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "brand")


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 0
    ordering = ("display_order", "value")


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ("product", "name", "display_order")
    list_filter = ("product",)
    inlines = [ProductAttributeValueInline]
    ordering = ("product", "display_order", "name")


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ("attribute", "value", "display_order")
    list_filter = ("attribute__product",)


class VariantImageInline(admin.TabularInline):
    model = VariantImage
    extra = 0


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("product", "price", "stock_quantity", "sku", "is_active", "display_order")
    list_filter = ("product", "is_active")
    inlines = [VariantImageInline]
    ordering = ("product", "display_order", "id")


@admin.register(VariantImage)
class VariantImageAdmin(admin.ModelAdmin):
    list_display = ("variant", "is_primary", "display_order")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "status", "updated_at")
    list_filter = ("status",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "selected_variant", "quantity", "unit_price")
    list_select_related = ("product", "selected_variant")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "display_customer", "display_email", "display_phone", "status", "total", "payment_status", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number", "user__email", "user__username", "address__email", "address__phone", "address__full_name")
    list_select_related = ("address", "user")

    def display_customer(self, obj):
        if obj.user_id is None:
            return "Guest Order"
        return getattr(obj.user, "email", None) or getattr(obj.user, "username", str(obj.user))
    display_customer.short_description = "Customer"

    def display_email(self, obj):
        return (obj.address.email or "—") if obj.address_id else "—"
    display_email.short_description = "Email"

    def display_phone(self, obj):
        return (obj.address.phone or "—") if obj.address_id else "—"
    display_phone.short_description = "Phone"

    def payment_status(self, obj):
        try:
            return obj.payment.get_status_display() if getattr(obj, "payment", None) else "—"
        except Exception:
            return "—"
    payment_status.short_description = "Payment"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "variant_snapshot", "quantity", "unit_price")
    list_select_related = ("order", "product", "selected_variant")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "city", "state", "is_snapshot")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "status", "amount", "processed_at")
    list_select_related = ("order", "order__address", "order__user")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_resolved", "created_at")
    list_filter = ("is_resolved",)


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "created_at")


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "selected_variant", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "user__username", "selected_variant__product__name")
    readonly_fields = ("user", "selected_variant", "created_at", "updated_at")
    ordering = ("-created_at",)
    list_select_related = ("user", "selected_variant", "selected_variant__product")

    def has_add_permission(self, request):
        return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_approved", "is_deleted", "created_at")
    list_filter = ("is_approved", "is_deleted", "rating")
