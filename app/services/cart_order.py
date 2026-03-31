import threading
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string

from ..models import (
    Address,
    Cart,
    CartItem,
    Order,
    OrderItem,
    Payment,
    Product,
    Variant,
    Wishlist,
)

from django.template.loader import render_to_string


def send_order_notification_email_async(order, request=None):
    """Send order notification email asynchronously in a background thread."""
    thread = threading.Thread(
        target=send_order_notification_email,
        args=(order, request),
        daemon=True
    )
    thread.start()
    return thread


def send_order_notification_email(order, request=None):
    """Send order notification email to admin/owner when a new order is placed."""
    try:
        admin_emails = getattr(settings, 'ADMIN_NOTIFICATION_EMAILS', [])
        if not admin_emails:
            return False

        try:
            if request:
                order_url = request.build_absolute_uri(f'/dashboard/orders/{order.order_number}/')
            else:
                site_domain = getattr(settings, 'SITE_DOMAIN', 'https://queenorange.shop/')
                order_url = f"{site_domain}/dashboard/orders/{order.order_number}/"
        except Exception:
            order_url = f"Order #{order.order_number}"

        payment_method = "Cash on Delivery"
        try:
            if hasattr(order, 'payment') and order.payment:
                payment_method = order.payment.get_method_display()
        except Exception:
            pass

        context = {
            'order': order,
            'order_url': order_url,
            'payment_method': payment_method,
            'site_name': ' Zanha Design',
        }

        try:
            html_message = render_to_string('admin/order_notification_email.html', context)
            plain_message = render_to_string('admin/order_notification_email.txt', context)
        except Exception:
            return False

        try:
            send_mail(
                subject=f'New Order #{order.order_number} - ₹{order.total}',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception:
            return False
    except Exception:
        return False


def send_order_confirmation_email(order):
    """
    Send customer email tailored to current order.status (best-effort).
    Priority for recipient:
    1) Order address email (if present)
    2) Logged-in user's email
    """
    try:
        from ..models import Order  # local import to avoid cycles at import time

        customer_email = ""
        try:
            if getattr(order, "address", None) and getattr(order.address, "email", ""):
                customer_email = (order.address.email or "").strip()
        except Exception:
            customer_email = ""

        if not customer_email and getattr(order, "user", None):
            customer_email = (getattr(order.user, "email", "") or "").strip()

        if not customer_email:
            return False

        status = getattr(order, "status", None)
        if status == Order.Status.CONFIRMED:
            status_key = "confirmed"
            subject = f"Your order #{order.order_number} is confirmed"
        elif status == Order.Status.SHIPPED:
            status_key = "shipped"
            subject = f"Good news! Order #{order.order_number} is on the way"
        elif status == Order.Status.DELIVERED:
            status_key = "delivered"
            subject = f"Order #{order.order_number} has been delivered"
        elif status == Order.Status.CANCELLED:
            status_key = "cancelled"
            subject = f"Order #{order.order_number} has been cancelled"
        else:
            status_key = "placed"
            subject = f"Thank you for your order #{order.order_number}"

        context = {
            "order": order,
            "site_name": "Zanha Jewels",
            "status_key": status_key,
        }
        try:
            html_message = render_to_string("emails/order_confirmation.html", context)
            plain_message = render_to_string("emails/order_confirmation.txt", context)
        except Exception:
            if status_key == "cancelled":
                plain_message = (
                    f"Your order #{order.order_number} has been cancelled. "
                    "If you did not request this, please contact support."
                )
            elif status_key == "shipped":
                plain_message = (
                    f"Your order #{order.order_number} has been shipped. "
                    "You'll receive another update when it is delivered."
                )
            elif status_key == "delivered":
                plain_message = (
                    f"Your order #{order.order_number} has been delivered. "
                    "We hope you enjoy your purchase!"
                )
            elif status_key == "confirmed":
                plain_message = (
                    f"Your order #{order.order_number} is confirmed. "
                    "We'll let you know once it ships."
                )
            else:
                plain_message = (
                    f"Thank you for your order #{order.order_number}. "
                    "We will notify you as it is confirmed and shipped."
                )
            html_message = None

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_email],
            html_message=html_message,
            fail_silently=True,
        )
        return True
    except Exception:
        return False


def send_order_confirmation_email_async(order):
    """Run customer confirmation email in a background thread."""
    try:
        thread = threading.Thread(
            target=send_order_confirmation_email,
            args=(order,),
            daemon=True,
        )
        thread.start()
        return thread
    except Exception:
        return None


def send_order_confirmation_email(order):
    """
    Send order confirmation email to customer (best-effort).
    Priority:
    1) Order address email (if present)
    2) Logged-in user's email
    """
    try:
        customer_email = ""
        try:
            if getattr(order, "address", None) and getattr(order.address, "email", ""):
                customer_email = (order.address.email or "").strip()
        except Exception:
            customer_email = ""

        if not customer_email and getattr(order, "user", None):
            customer_email = (getattr(order.user, "email", "") or "").strip()

        if not customer_email:
            return False

        context = {
            "order": order,
            "site_name": "Zanha Jewels",
        }
        try:
            html_message = render_to_string("emails/order_confirmation.html", context)
            plain_message = render_to_string("emails/order_confirmation.txt", context)
        except Exception:
            plain_message = f"Thank you for your order #{order.order_number}. We will notify you when it ships."
            html_message = None

        send_mail(
            subject=f"Your order #{order.order_number} has been placed",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_email],
            html_message=html_message,
            fail_silently=True,
        )
        return True
    except Exception:
        return False


class CartError(Exception):
    pass


class StockError(CartError):
    pass


@dataclass
class CartTotals:
    subtotal: object
    gst_total: object
    shipping: object
    total: object


class CartService:
    @staticmethod
    def _ensure_session_key(request):
        if not request.session.session_key:
            request.session.save()
        return request.session.session_key

    @classmethod
    def get_or_create_cart(cls, request):
        user = getattr(request, "user", None)
        user = user if (user and user.is_authenticated) else None
        if user:
            cart, _ = Cart.objects.get_or_create(user=user, status=Cart.Status.ACTIVE)
            return cart
        session_key = cls._ensure_session_key(request)
        cart = Cart.objects.filter(
            session_key=session_key, status=Cart.Status.ACTIVE, user__isnull=True
        ).first()
        if not cart:
            cart = Cart.objects.create(session_key=session_key, status=Cart.Status.ACTIVE)
        return cart

    @classmethod
    def merge_carts(cls, user, session_key):
        if not user or not session_key:
            return
        try:
            session_cart = Cart.objects.get(session_key=session_key, status=Cart.Status.ACTIVE)
        except Cart.DoesNotExist:
            return
        user_cart, _ = Cart.objects.get_or_create(user=user, status=Cart.Status.ACTIVE)
        for item in session_cart.items.select_related("product", "selected_variant").all():
            if item.selected_variant_id:
                cls.add_item(user_cart, item.selected_variant, item.quantity)
        session_cart.status = Cart.Status.ABANDONED
        session_cart.save(update_fields=["status"])

    @staticmethod
    def merge_session_wishlist_to_user(request, user):
        """Merge session wishlist (variant IDs) into user's DB wishlist. Call after login."""
        if not user or not user.is_authenticated:
            return
        variant_ids = list(request.session.get("wishlist") or [])
        if not variant_ids:
            return
        seen = set()
        for vid in variant_ids[:50]:
            try:
                vid = int(vid)
            except (TypeError, ValueError):
                continue
            if vid in seen:
                continue
            seen.add(vid)
            v = (
                Variant.objects.filter(
                    pk=vid, is_active=True, product__is_active=True
                ).first()
            )
            if not v:
                continue
            Wishlist.objects.get_or_create(
                user=user, selected_variant=v
            )
        request.session.pop("wishlist", None)

    # @staticmethod
    # def compute_totals(cart):
    #     try:
    #         subtotal = sum(item.line_total for item in cart.items.select_related("product"))
    #         gst_total = cart.gst_total

    #         # Import inside function to avoid circulars during app loading
    #         from ..delivery_utils import delivery_enabled

    #         FREE_SHIPPING_THRESHOLD = getattr(settings, "FREE_SHIPPING_ABOVE", 999)
    #         delivery_charge = getattr(settings, "FLAT_DELIVERY_CHARGE", 100)

    #         if delivery_enabled():
    #             shipping = 0 if subtotal >= FREE_SHIPPING_THRESHOLD else delivery_charge
    #         else:
    #             # When delivery integration is disabled, treat shipping as zero
    #             shipping = 0

    #         total = subtotal + gst_total + shipping
    #         return CartTotals(subtotal=subtotal, gst_total=gst_total, shipping=shipping, total=total)
    #     except Exception:
    #         return CartTotals(subtotal=0, gst_total=0, shipping=0, total=0)
    @staticmethod
    def compute_totals(cart): #No Shiprocket, no delivery_enabled(), just flat ₹80 below ₹999 and free above.
        try:
            subtotal = sum(item.line_total for item in cart.items.select_related("product"))
            gst_total = cart.gst_total

            FREE_SHIPPING_THRESHOLD = getattr(settings, "FREE_SHIPPING_ABOVE", 999)
            delivery_charge = getattr(settings, "FLAT_DELIVERY_CHARGE", 60)

            shipping = 0 if subtotal >= FREE_SHIPPING_THRESHOLD else delivery_charge

            total = subtotal + gst_total + shipping
            return CartTotals(subtotal=subtotal, gst_total=gst_total, shipping=shipping, total=total)
        except Exception:
            return CartTotals(subtotal=0, gst_total=0, shipping=0, total=0)

    @staticmethod
    def add_item(cart, variant, quantity):
        """
        Add an item to the cart.

        Backwards-compatible behaviour:
        - If `variant` is a Variant instance (normal flow): behaves as before.
        - If `variant` is a Product instance for a simple product (no variants):
          treats it as a virtual variant and uses Product.base_price/base_stock.
        """
        # Simple-product path: `variant` is actually a Product
        from ..models import Product  # local import to avoid cycles

        if isinstance(variant, Product):
            product = variant
            if product.has_variants():
                raise CartError("Invalid simple product. Variants exist for this product.")
            unit_price = product.base_price
            base_stock = product.base_stock or 0
            if not unit_price or base_stock <= 0:
                raise StockError("This item is out of stock.")
            max_qty = getattr(settings, "MAX_CART_QTY", 10)
            quantity = max(1, min(quantity, max_qty))
            if quantity > base_stock:
                raise StockError("Requested quantity exceeds available stock.")

            # For simple products we store selected_variant as NULL and key uniqueness by (cart, product, selected_variant IS NULL)
            item = CartItem.objects.filter(cart=cart, product=product, selected_variant__isnull=True).first()
            if item:
                new_quantity = min(item.quantity + quantity, max_qty)
                if new_quantity > base_stock:
                    raise StockError("Requested quantity exceeds available stock.")
                item.quantity = new_quantity
                item.unit_price = unit_price
                item.save(update_fields=["quantity", "unit_price", "updated_at"])
                return item
            return CartItem.objects.create(
                cart=cart,
                product=product,
                selected_variant=None,
                quantity=quantity,
                unit_price=unit_price,
            )

        # Variant-based product (existing behaviour)
        if not isinstance(variant, Variant):
            raise CartError("Invalid variant.")
        v = variant
        product = v.product
        if not getattr(v, "is_active", True) or (v.stock_quantity or 0) <= 0:
            raise StockError("This item is out of stock.")
        max_qty = getattr(settings, "MAX_CART_QTY", 10)
        quantity = max(1, min(quantity, max_qty))
        if quantity > v.stock_quantity:
            raise StockError("Requested quantity exceeds available stock.")
        item = CartItem.objects.filter(cart=cart, selected_variant=v).first()
        if item:
            new_quantity = min(item.quantity + quantity, max_qty)
            if new_quantity > v.stock_quantity:
                raise StockError("Requested quantity exceeds available stock.")
            item.quantity = new_quantity
            item.unit_price = v.price
            item.save(update_fields=["quantity", "unit_price", "updated_at"])
            return item
        return CartItem.objects.create(
            cart=cart,
            product=product,
            selected_variant=v,
            quantity=quantity,
            unit_price=v.price,
        )

    @staticmethod
    def update_item(item, quantity):
        if quantity <= 0:
            item.delete()
            return
        v = item.selected_variant
        # Simple product (no concrete variant)
        if not v:
            product = item.product
            if product.has_variants():
                raise CartError("Invalid cart item.")
            stock = product.base_stock or 0
            unit_price = product.base_price
        else:
            stock = v.stock_quantity
            unit_price = v.price
        max_qty = getattr(settings, "MAX_CART_QTY", 10)
        quantity = min(quantity, max_qty)
        if quantity > stock:
            raise StockError("Requested quantity exceeds available stock.")
        item.quantity = quantity
        item.unit_price = unit_price
        item.save(update_fields=["quantity", "unit_price", "updated_at"])


class OrderService:
    @staticmethod
    def _generate_order_number():
        while True:
            order_number = f"QO{get_random_string(8).upper()}"
            if not Order.objects.filter(order_number=order_number).exists():
                return order_number

    @classmethod
    @transaction.atomic
    def create_order(cls, cart, form_data, user=None, clear_cart=True):
        if cart.status != Cart.Status.ACTIVE:
            raise CartError("This cart has already been used for an order.")
        items = (
            cart.items.select_related("selected_variant", "product")
            .select_for_update(of=("self",))
            .all()
        )
        if not items:
            raise CartError("Cart is empty.")

        for item in items:
            product = item.product
            if not getattr(product, "is_active", True):
                raise CartError(f"{product.name} is no longer available.")
            v = item.selected_variant
            if v:
                if item.quantity > v.stock_quantity:
                    raise StockError(f"{product.name} is out of stock.")
            else:
                # Simple product without variants: validate against base_stock
                if product.has_variants():
                    raise CartError("Invalid cart item.")
                base_stock = product.base_stock or 0
                if item.quantity > base_stock:
                    raise StockError(f"{product.name} is out of stock.")

        selected_address_id = form_data.get('selected_address')
        use_new_address = form_data.get('use_new_address', False)

        if selected_address_id and not use_new_address and user:
            try:
                existing_address = Address.objects.get(pk=selected_address_id, user=user, is_snapshot=False)
                address = Address.objects.create(
                    user=user,
                    full_name=existing_address.full_name,
                    phone=existing_address.phone,
                    email=existing_address.email,
                    address_line=existing_address.address_line,
                    city=existing_address.city,
                    state=existing_address.state,
                    pincode=existing_address.pincode,
                    is_snapshot=True,
                )
            except Address.DoesNotExist:
                raise CartError("Selected address not found.")
        else:
            # New address entered on checkout.
            # For logged-in users, persist it as a reusable address (is_snapshot=False)
            # and also create a snapshot for the order. For guests, only create snapshot.
            user_obj = user if user is not None else cart.user
            full_name = form_data["full_name"]
            phone = form_data["phone"]
            email = form_data.get("email", "")
            address_line = form_data["address_line"]
            city = form_data["city"]
            state = form_data["state"]
            pincode = form_data["pincode"]

            if user_obj:
                # Decide if this should be default: first address becomes default by default.
                has_any_saved = Address.objects.filter(user=user_obj, is_snapshot=False).exists()
                saved_address = Address.objects.create(
                    user=user_obj,
                    full_name=full_name,
                    phone=phone,
                    email=email,
                    address_line=address_line,
                    city=city,
                    state=state,
                    pincode=pincode,
                    is_default=not has_any_saved,
                    is_snapshot=False,
                )
                address = Address.objects.create(
                    user=user_obj,
                    full_name=saved_address.full_name,
                    phone=saved_address.phone,
                    email=saved_address.email,
                    address_line=saved_address.address_line,
                    city=saved_address.city,
                    state=saved_address.state,
                    pincode=saved_address.pincode,
                    is_snapshot=True,
                )
            else:
                address = Address.objects.create(
                    user=None,
                    full_name=full_name,
                    phone=phone,
                    email=email,
                    address_line=address_line,
                    city=city,
                    state=state,
                    pincode=pincode,
                    is_snapshot=True,
                )

        totals = CartService.compute_totals(cart)
        order_number = cls._generate_order_number()
        gst_total = getattr(totals, "gst_total", 0) or 0
        state = (address.state or "").strip()
        if state and state.lower() == "kerala":
            cgst = gst_total / 2
            sgst = gst_total / 2
            igst = 0
        else:
            cgst = 0
            sgst = 0
            igst = gst_total
        order = Order.objects.create(
            user=cart.user if cart.user else None,
            order_number=order_number,
            subtotal=totals.subtotal,
            shipping=totals.shipping,
            gst_total=gst_total,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            total=totals.total,
            address=address,
        )

        for item in items:
            v = item.selected_variant
            product = item.product
            # For simple products, use a default variant snapshot label
            snapshot = v.get_attribute_values_display() if v else "Default"
            taxable_value = 0
            gst_amount = 0
            hsn_code = None
            gst_percentage = None
            if getattr(product, "is_gst_applicable", False) and getattr(product, "gst_percentage", None) is not None:
                from decimal import Decimal
                taxable_value = item.unit_price * item.quantity
                gst_amount = taxable_value * (product.gst_percentage / Decimal("100"))
                hsn_code = getattr(product, "hsn_code", None) or None
                gst_percentage = product.gst_percentage

            OrderItem.objects.create(
                order=order,
                product=product,
                selected_variant=v,
                product_name=product.name,
                variant_snapshot=snapshot or product.name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                hsn_code=hsn_code,
                gst_percentage=gst_percentage,
                taxable_value=taxable_value,
                gst_amount=gst_amount,
            )
            if form_data.get("payment") != Payment.Method.RAZORPAY:
                if v:
                    Variant.objects.filter(pk=item.selected_variant_id).update(
                        stock_quantity=F("stock_quantity") - item.quantity
                    )
                else:
                    # Simple product: decrement base_stock on the product
                    Product.objects.filter(pk=product.pk).update(
                        base_stock=F("base_stock") - item.quantity
                    )

        Payment.objects.create(
            order=order,
            method=form_data.get("payment", Payment.Method.COD),
            amount=totals.total,
        )

        if clear_cart:
            cart.status = Cart.Status.ORDERED
            cart.save(update_fields=["status"])
            cart.items.all().delete()

        send_order_notification_email_async(order)

        return order
