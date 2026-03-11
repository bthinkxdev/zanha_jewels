"""Modular Product EDIT and CREATE API views. Attribute-based variants only."""
import json
import logging

from django import forms
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, View

from .models import (
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductImage,
    Variant,
    VariantAttributeValue,
    VariantImage,
)
from .admin_forms import ProductBasicEditForm, _validate_image_file

logger = logging.getLogger(__name__)


def _normalize_payload(data):
    """Normalise empty strings to None for optional fields."""
    if data.get("slug") == "":
        data["slug"] = None
    if data.get("description") == "":
        data["description"] = ""
    if data.get("brand") == "":
        data["brand"] = ""
    if data.get("deal_of_day_start") == "":
        data["deal_of_day_start"] = None
    if data.get("deal_of_day_end") == "":
        data["deal_of_day_end"] = None
    if data.get("gst_percentage") == "" or data.get("gst_percentage") is None:
        data["gst_percentage"] = None
    if data.get("hsn_code") == "":
        data["hsn_code"] = None
    return data


class ProductCreateBasicView(View):
    """POST /admin/products/create-basic/ — JSON body, create product only."""
    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        _normalize_payload(data)
        if data.get("category") == "":
            data["category"] = None
        form = ProductBasicEditForm(data, instance=None)
        if not form.is_valid():
            errors = {k: list(v) for k, v in form.errors.items()}
            return JsonResponse({"success": False, "errors": errors}, status=400)
        product = form.save()
        return JsonResponse({"success": True, "product_id": product.pk})


class ProductEditView(DetailView):
    """GET only. Renders modular edit dashboard."""
    model = Product
    template_name = "admin/product_edit.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.prefetch_related(
            "attributes__values",
            "variants__attribute_values__attribute",
            "variants__images",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "products"
        context["form_title"] = "Edit Product"
        context["basic_form"] = ProductBasicEditForm(instance=self.object)
        # Prefetch simple product images (for products without variants)
        context["base_images"] = list(
            ProductImage.objects.filter(product=self.object).order_by("display_order", "-is_primary", "id")[:3]
        )
        return context


class ProductUpdateBasicView(View):
    """POST /admin/products/<id>/update-basic/ — JSON body."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        _normalize_payload(data)
        form = ProductBasicEditForm(data, instance=product)
        if not form.is_valid():
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        form.save(commit=False)
        update_fields = [f for f in form.changed_data if f in form.Meta.fields]
        if "name" in update_fields and "slug" not in update_fields:
            update_fields.append("slug")
        if update_fields:
            form.instance.save(update_fields=update_fields)
        return JsonResponse({"success": True})


class ProductToggleActiveView(View):
    """POST /admin/products/<id>/toggle-active/ — toggle or set is_active."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        if "is_active" in data:
            new_active = bool(data["is_active"])
        else:
            new_active = not product.is_active
        product.is_active = new_active
        product.save(update_fields=["is_active"])
        return JsonResponse({"success": True, "is_active": new_active})


# --- Attributes ---

class ProductAttributesListApiView(View):
    """GET /admin/products/<pk>/attributes/ — list attributes with values."""
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        attributes = product.attributes.prefetch_related("values").order_by("display_order", "name")
        out = []
        for attr in attributes:
            values = [
                {"id": v.id, "value": v.value, "display_order": v.display_order}
                for v in attr.values.order_by("display_order", "value")
            ]
            out.append({
                "id": attr.id,
                "name": attr.name,
                "display_order": attr.display_order,
                "values": values,
            })
        return JsonResponse({"attributes": out})


class ProductAttributeCreateApiView(View):
    """POST /admin/products/<pk>/attributes/add/ — add attribute. No duplicate name per product."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        name = (data.get("name") or "").strip()
        if not name:
            return JsonResponse({"success": False, "errors": {"name": ["Name is required."]}}, status=400)
        if product.attributes.filter(name__iexact=name).exists():
            return JsonResponse({"success": False, "errors": {"name": ["This attribute name already exists for this product."]}}, status=400)
        display_order = data.get("display_order")
        if display_order is None:
            display_order = product.attributes.count()
        try:
            display_order = int(display_order)
        except (TypeError, ValueError):
            display_order = product.attributes.count()
        attr = ProductAttribute.objects.create(
            product=product,
            name=name,
            display_order=display_order,
        )
        return JsonResponse({
            "success": True,
            "attribute": {"id": attr.id, "name": attr.name, "display_order": attr.display_order, "values": []},
        })


class ProductAttributeUpdateApiView(View):
    """POST /admin/attributes/<int:attr_id>/update/."""
    def post(self, request, attr_id):
        attr = get_object_or_404(ProductAttribute, pk=attr_id)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        name = (data.get("name") or "").strip()
        if not name:
            return JsonResponse({"success": False, "errors": {"name": ["Name is required."]}}, status=400)
        if attr.product.attributes.filter(name__iexact=name).exclude(pk=attr.pk).exists():
            return JsonResponse({"success": False, "errors": {"name": ["This attribute name already exists."]}}, status=400)
        update_kw = {"name": name}
        if "display_order" in data:
            try:
                update_kw["display_order"] = int(data["display_order"])
            except (TypeError, ValueError):
                pass
        ProductAttribute.objects.filter(pk=attr.pk).update(**update_kw)
        return JsonResponse({"success": True})


class ProductAttributeDeleteApiView(View):
    """POST /admin/attributes/<int:attr_id>/delete/."""
    def post(self, request, attr_id):
        attr = get_object_or_404(ProductAttribute, pk=attr_id)
        attr.delete()
        return JsonResponse({"success": True})


class ProductAttributeValueCreateApiView(View):
    """POST /admin/attributes/<int:attr_id>/values/add/."""
    def post(self, request, attr_id):
        attr = get_object_or_404(ProductAttribute, pk=attr_id)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        value = (data.get("value") or "").strip()
        if not value:
            return JsonResponse({"success": False, "errors": {"value": ["Value is required."]}}, status=400)
        if attr.values.filter(value__iexact=value).exists():
            return JsonResponse({"success": False, "errors": {"value": ["This value already exists for this attribute."]}}, status=400)
        display_order = data.get("display_order")
        if display_order is None:
            display_order = attr.values.count()
        try:
            display_order = int(display_order)
        except (TypeError, ValueError):
            display_order = attr.values.count()
        av = ProductAttributeValue.objects.create(
            attribute=attr,
            value=value,
            display_order=display_order,
        )
        return JsonResponse({"success": True, "attribute_value": {"id": av.id, "value": av.value, "display_order": av.display_order}})


class ProductAttributeValueUpdateApiView(View):
    """POST /admin/attribute-values/<int:av_id>/update/."""
    def post(self, request, av_id):
        av = get_object_or_404(ProductAttributeValue, pk=av_id)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        value = (data.get("value") or "").strip()
        if not value:
            return JsonResponse({"success": False, "errors": {"value": ["Value is required."]}}, status=400)
        if av.attribute.values.filter(value__iexact=value).exclude(pk=av.pk).exists():
            return JsonResponse({"success": False, "errors": {"value": ["This value already exists."]}}, status=400)
        update_kw = {"value": value}
        if "display_order" in data:
            try:
                update_kw["display_order"] = int(data["display_order"])
            except (TypeError, ValueError):
                pass
        ProductAttributeValue.objects.filter(pk=av.pk).update(**update_kw)
        return JsonResponse({"success": True})


class ProductAttributeValueDeleteApiView(View):
    """POST /admin/attribute-values/<int:av_id>/delete/."""
    def post(self, request, av_id):
        av = get_object_or_404(ProductAttributeValue, pk=av_id)
        av.delete()
        return JsonResponse({"success": True})


# --- Variants ---

def _decimal_from_data(data, key, default=0):
    """Parse a non-negative decimal from JSON data. Returns default if missing/invalid."""
    from decimal import Decimal
    val = data.get(key)
    if val is None or val == "":
        return default if default is not None else Decimal("0")
    try:
        d = Decimal(str(val).strip())
        return d if d >= 0 else (default if default is not None else Decimal("0"))
    except Exception:
        return default if default is not None else Decimal("0")


def _variant_payload(v):
    """Serialize variant for JSON (with attribute_values and images)."""
    values = [
        {"id": av.id, "attribute_id": av.attribute_id, "attribute_name": av.attribute.name, "value": av.value}
        for av in v.attribute_values.select_related("attribute").order_by("attribute__display_order", "display_order")
    ]
    images = [
        {"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary, "display_order": img.display_order}
        for img in v.images.order_by("display_order", "-is_primary", "id")
    ]
    return {
        "id": v.id,
        "attribute_values": values,
        "price": str(v.price),
        "stock_quantity": v.stock_quantity,
        "sku": v.sku or "",
        "is_active": v.is_active,
        "display_order": v.display_order,
        "weight": str(getattr(v, "weight", 0) or 0),
        "length": str(getattr(v, "length", 0) or 0),
        "breadth": str(getattr(v, "breadth", 0) or 0),
        "height": str(getattr(v, "height", 0) or 0),
        "images": images,
    }


class ProductVariantsListApiView(View):
    """GET /admin/products/<pk>/variants/ — list variants with attribute_values and images."""
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        variants = product.variants.prefetch_related(
            "attribute_values__attribute",
            "images",
        ).order_by("display_order", "id")
        out = [_variant_payload(v) for v in variants]
        return JsonResponse({"variants": out})


def _check_unique_variant_combination(product, attribute_value_ids, exclude_variant_id=None):
    """Ensure no other variant of this product has the same set of attribute value IDs. Return (True, None) or (False, error_msg)."""
    value_ids = set(attribute_value_ids)
    if not value_ids:
        return True, None
    others = product.variants.prefetch_related("attribute_values").exclude(pk=exclude_variant_id or 0)
    for other in others:
        other_ids = set(other.attribute_values.values_list("id", flat=True))
        if other_ids == value_ids:
            return False, "A variant with this combination of options already exists."
    return True, None


class VariantCreateApiView(View):
    """POST /admin/products/<pk>/variants/add/ — create variant. attribute_value_ids, price, stock_quantity, sku, display_order, is_active."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        price = data.get("price")
        if price is None or price == "":
            return JsonResponse({"success": False, "errors": {"price": ["Price is required."]}}, status=400)
        try:
            from decimal import Decimal
            price = Decimal(str(price).strip())
            if price < 0:
                raise ValueError("negative")
        except Exception:
            return JsonResponse({"success": False, "errors": {"price": ["Enter a valid price."]}}, status=400)
        attribute_value_ids = data.get("attribute_value_ids") or []
        if not isinstance(attribute_value_ids, list):
            attribute_value_ids = []
        # Validate all ids belong to this product's attributes
        valid_ids = set(
            ProductAttributeValue.objects.filter(
                attribute__product=product
            ).values_list("id", flat=True)
        )
        attribute_value_ids = [int(x) for x in attribute_value_ids if int(x) in valid_ids]
        # Variant must have at least 1 attribute value
        if not attribute_value_ids:
            return JsonResponse(
                {"success": False, "errors": {"attribute_value_ids": ["Select at least one attribute value."]}},
                status=400,
            )
        ok, err = _check_unique_variant_combination(product, attribute_value_ids)
        if not ok:
            return JsonResponse({"success": False, "errors": {"attribute_value_ids": [err]}}, status=400)
        stock_quantity = data.get("stock_quantity")
        if stock_quantity is None:
            stock_quantity = 0
        try:
            stock_quantity = max(0, int(stock_quantity))
        except (TypeError, ValueError):
            stock_quantity = 0
        sku = (data.get("sku") or "").strip() or None
        if sku and Variant.objects.filter(sku=sku).exists():
            return JsonResponse({"success": False, "errors": {"sku": ["This SKU is already in use."]}}, status=400)
        display_order = data.get("display_order")
        if display_order is None:
            display_order = product.variants.count()
        try:
            display_order = int(display_order)
        except (TypeError, ValueError):
            display_order = product.variants.count()
        is_active = data.get("is_active", True)
        weight = _decimal_from_data(data, "weight", 0)
        length = _decimal_from_data(data, "length", 0)
        breadth = _decimal_from_data(data, "breadth", 0)
        height = _decimal_from_data(data, "height", 0)
        with transaction.atomic():
            v = Variant.objects.create(
                product=product,
                price=price,
                stock_quantity=stock_quantity,
                sku=sku,
                display_order=display_order,
                is_active=bool(is_active),
                weight=weight,
                length=length,
                breadth=breadth,
                height=height,
            )
            v.attribute_values.set(ProductAttributeValue.objects.filter(id__in=attribute_value_ids))
        v = Variant.objects.prefetch_related("attribute_values__attribute", "images").get(pk=v.pk)
        return JsonResponse({"success": True, "variant": _variant_payload(v)})


class VariantUpdateApiView(View):
    """POST /admin/variants/<int:variant_id>/update/."""
    def post(self, request, variant_id):
        v = get_object_or_404(Variant, pk=variant_id)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        update_kw = {}
        if "price" in data:
            try:
                from decimal import Decimal
                p = Decimal(str(data["price"]).strip())
                if p >= 0:
                    update_kw["price"] = p
            except Exception:
                pass
        if "stock_quantity" in data:
            try:
                q = int(data["stock_quantity"])
                if q >= 0:
                    update_kw["stock_quantity"] = q
            except (TypeError, ValueError):
                pass
        if "sku" in data:
            sku = (data.get("sku") or "").strip() or None
            if sku and Variant.objects.filter(sku=sku).exclude(pk=v.pk).exists():
                return JsonResponse({"success": False, "errors": {"sku": ["This SKU is already in use."]}}, status=400)
            update_kw["sku"] = sku
        if "display_order" in data:
            try:
                update_kw["display_order"] = int(data["display_order"])
            except (TypeError, ValueError):
                pass
        if "is_active" in data:
            update_kw["is_active"] = bool(data["is_active"])
        for field in ("weight", "length", "breadth", "height"):
            if field in data:
                val = _decimal_from_data(data, field, None)
                if val is not None and val >= 0:
                    update_kw[field] = val
        attribute_value_ids = data.get("attribute_value_ids")
        if attribute_value_ids is not None:
            if not isinstance(attribute_value_ids, list):
                attribute_value_ids = []
            valid_ids = set(
                ProductAttributeValue.objects.filter(attribute__product=v.product).values_list("id", flat=True)
            )
            ids = [int(x) for x in attribute_value_ids if int(x) in valid_ids]
            ok, err = _check_unique_variant_combination(v.product, ids, exclude_variant_id=v.pk)
            if not ok:
                return JsonResponse({"success": False, "errors": {"attribute_value_ids": [err]}}, status=400)
            v.attribute_values.set(ProductAttributeValue.objects.filter(id__in=ids))
        if update_kw:
            Variant.objects.filter(pk=v.pk).update(**update_kw)
        v.refresh_from_db()
        return JsonResponse({"success": True, "variant": _variant_payload(v)})


class VariantDeleteApiView(View):
    """POST /admin/variants/<int:variant_id>/delete/."""
    def post(self, request, variant_id):
        v = get_object_or_404(Variant, pk=variant_id)
        v.delete()
        return JsonResponse({"success": True})


class VariantUploadImageView(View):
    """POST /admin/variants/<int:variant_id>/upload-image/ — multipart."""
    def post(self, request, variant_id):
        v = get_object_or_404(Variant, pk=variant_id)
        image_file = request.FILES.get("image")
        if not image_file:
            return JsonResponse({"success": False, "errors": {"image": ["No file provided."]}}, status=400)
        try:
            _validate_image_file(image_file, required=True)
        except forms.ValidationError as e:
            return JsonResponse({"success": False, "errors": {"image": [str(m) for m in e.messages]}}, status=400)
        is_primary = v.images.count() == 0
        display_order = v.images.count()
        img = VariantImage.objects.create(
            variant=v,
            image=image_file,
            is_primary=is_primary,
            display_order=display_order,
        )
        return JsonResponse({
            "success": True,
            "image": {"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary, "display_order": img.display_order},
        })


class VariantImageDeleteView(View):
    """POST /admin/variant-images/<int:image_id>/delete/."""
    def post(self, request, image_id):
        img = get_object_or_404(VariantImage, pk=image_id)
        image_name = img.image.name if img.image else None
        storage = img.image.storage if img.image else None
        img.delete()
        if image_name and storage:
            try:
                storage.delete(image_name)
            except Exception:
                pass
        return JsonResponse({"success": True})


class VariantImageSetPrimaryView(View):
    """POST /admin/variant-images/<int:image_id>/set-primary/ — set this image as primary, unset others."""
    def post(self, request, image_id):
        img = get_object_or_404(VariantImage, pk=image_id)
        variant = img.variant
        VariantImage.objects.filter(variant=variant).update(is_primary=False)
        img.is_primary = True
        img.save(update_fields=["is_primary"])
        return JsonResponse({"success": True})


class VariantImageReorderView(View):
    """POST /admin/variant-images/reorder/ — body: { variant_id: int, order: [image_id, ...] }."""
    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        variant_id = data.get("variant_id")
        order = data.get("order")
        if not variant_id or not isinstance(order, list):
            return JsonResponse(
                {"success": False, "errors": {"__all__": ["variant_id and order (list) required."]}},
                status=400,
            )
        variant = get_object_or_404(Variant, pk=variant_id)
        for display_order, image_id in enumerate(order):
            VariantImage.objects.filter(variant=variant, pk=image_id).update(display_order=display_order)
        return JsonResponse({"success": True})


# --- Simple product images (ProductImage) ---


class ProductImageUploadView(View):
    """POST /admin/products/<int:product_id>/base-images/upload/ — multipart. Max 3 images. Only when product has no variants."""

    def post(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        if product.variants.exists():
            return JsonResponse(
                {"success": False, "errors": {"__all__": ["Base images are ignored when variants exist."]}},
                status=400,
            )
        if product.images.count() >= 3:
            return JsonResponse(
                {"success": False, "errors": {"image": ["You can upload a maximum of 3 images for a simple product."]}},
                status=400,
            )
        image_file = request.FILES.get("image")
        if not image_file:
            return JsonResponse({"success": False, "errors": {"image": ["No file provided."]}}, status=400)
        try:
            _validate_image_file(image_file, required=True)
        except forms.ValidationError as e:
            return JsonResponse({"success": False, "errors": {"image": [str(m) for m in e.messages]}}, status=400)
        is_primary = product.images.count() == 0
        display_order = product.images.count()
        img = ProductImage.objects.create(
            product=product,
            image=image_file,
            is_primary=is_primary,
            display_order=display_order,
        )
        return JsonResponse(
            {
                "success": True,
                "image": {
                    "id": img.id,
                    "url": img.image.url if img.image else None,
                    "is_primary": img.is_primary,
                    "display_order": img.display_order,
                },
            }
        )


class ProductImageDeleteView(View):
    """POST /admin/products/base-images/<int:image_id>/delete/."""

    def post(self, request, image_id):
        img = get_object_or_404(ProductImage, pk=image_id)
        image_name = img.image.name if img.image else None
        storage = img.image.storage if img.image else None
        product = img.product
        img.delete()
        if image_name and storage:
            try:
                storage.delete(image_name)
            except Exception:
                pass
        # Ensure remaining images have contiguous display_order and one primary
        remaining = list(ProductImage.objects.filter(product=product).order_by("display_order", "-is_primary", "id"))
        for idx, im in enumerate(remaining):
            im.display_order = idx
            im.save(update_fields=["display_order"])
        if remaining and not any(im.is_primary for im in remaining):
            first = remaining[0]
            first.is_primary = True
            first.save(update_fields=["is_primary"])
        return JsonResponse({"success": True})


class ProductImageSetPrimaryView(View):
    """POST /admin/products/base-images/<int:image_id>/set-primary/."""

    def post(self, request, image_id):
        img = get_object_or_404(ProductImage, pk=image_id)
        ProductImage.objects.filter(product=img.product).update(is_primary=False)
        img.is_primary = True
        img.save(update_fields=["is_primary"])
        return JsonResponse({"success": True})


class ProductImageReorderView(View):
    """POST /admin/products/base-images/reorder/ — body: { product_id: int, order: [image_id, ...] }."""

    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        product_id = data.get("product_id")
        order = data.get("order")
        if not product_id or not isinstance(order, list):
            return JsonResponse(
                {"success": False, "errors": {"__all__": ["product_id and order (list) required."]}},
                status=400,
            )
        product = get_object_or_404(Product, pk=product_id)
        for display_order, image_id in enumerate(order):
            ProductImage.objects.filter(product=product, pk=image_id).update(display_order=display_order)
        return JsonResponse({"success": True})


class ProductAttributesReorderApiView(View):
    """POST /admin/products/<int:pk>/attributes/reorder/ — body: { order: [attr_id, ...] }."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        order = data.get("order")
        if not isinstance(order, list):
            return JsonResponse({"success": False, "errors": {"order": ["Order must be a list of attribute IDs."]}}, status=400)
        valid_ids = set(product.attributes.values_list("id", flat=True))
        for display_order, attr_id in enumerate(order):
            if attr_id in valid_ids:
                ProductAttribute.objects.filter(product=product, pk=attr_id).update(display_order=display_order)
        return JsonResponse({"success": True})


class ProductAttributeValuesReorderApiView(View):
    """POST /admin/attributes/<int:attr_id>/values/reorder/ — body: { order: [av_id, ...] }."""
    def post(self, request, attr_id):
        attr = get_object_or_404(ProductAttribute, pk=attr_id)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        order = data.get("order")
        if not isinstance(order, list):
            return JsonResponse({"success": False, "errors": {"order": ["Order must be a list of value IDs."]}}, status=400)
        valid_ids = set(attr.values.values_list("id", flat=True))
        for display_order, av_id in enumerate(order):
            if av_id in valid_ids:
                ProductAttributeValue.objects.filter(attribute=attr, pk=av_id).update(display_order=display_order)
        return JsonResponse({"success": True})
