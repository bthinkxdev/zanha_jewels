import logging

from django import forms
from django.conf import settings
from django.forms.formsets import DELETION_FIELD_NAME

from .models import Banner, Category, Product

logger = logging.getLogger(__name__)


def _validate_image_file(image, required=False):
    if not image and not required:
        return image
    if image and hasattr(image, "size"):
        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            raise forms.ValidationError(
                f"Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB"
            )
        try:
            from PIL import Image as PILImage
            img = PILImage.open(image)
            width, height = img.size
            if width * height > 5_000_000:
                raise forms.ValidationError(
                    "Image resolution cannot exceed 5 megapixels. Please resize or compress."
                )
            img.verify()
            image.seek(0)
        except forms.ValidationError:
            raise
        except Exception:
            raise forms.ValidationError(
                "Invalid image file. Please upload a valid image (JPG, PNG, GIF, WebP)."
            )
    return image


class AdminLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Username",
            "autocomplete": "username"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Password",
            "autocomplete": "current-password"
        })
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "is_active", "image"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Category Name"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "category-slug"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            max_size = 5 * 1024 * 1024
            if image.size > max_size:
                raise forms.ValidationError(f'Image file size cannot exceed 5MB.')
            try:
                from PIL import Image
                img = Image.open(image)
                width, height = img.size
                if width * height > 5_000_000:
                    raise forms.ValidationError('Image resolution cannot exceed 5 megapixels.')
                img.verify()
                image.seek(0)
            except forms.ValidationError:
                raise
            except Exception:
                raise forms.ValidationError('Invalid image file.')
        return image


def _validate_banner_image(image, required=True):
    if not image and not required:
        return image
    if not image and required:
        raise forms.ValidationError("Banner image is required.")
    if image and hasattr(image, "size"):
        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            raise forms.ValidationError(
                f"Image file size cannot exceed 5MB. Current size: {image.size / (1024 * 1024):.2f}MB"
            )
        try:
            from PIL import Image as PILImage
            img = PILImage.open(image)
            width, height = img.size
            if width * height > 5_000_000:
                raise forms.ValidationError(
                    "Image resolution cannot exceed 5 megapixels. Please resize or compress."
                )
            img.verify()
            image.seek(0)
        except forms.ValidationError:
            raise
        except Exception:
            raise forms.ValidationError(
                "Invalid image file. Please upload a valid image (JPG, PNG, GIF, WebP)."
            )
    return image


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ["title", "subtitle", "image", "redirect_url", "is_active", "display_order"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Banner title (optional)"}),
            "subtitle": forms.TextInput(attrs={"class": "form-control", "placeholder": "Banner subtitle (optional)"}),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "redirect_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://... (optional)"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "display_order": forms.NumberInput(attrs={"class": "form-control", "min": 0, "placeholder": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["subtitle"].required = False
        self.fields["redirect_url"].required = False
        if self.instance and self.instance.pk and self.instance.image:
            self.fields["image"].required = False

    def clean_image(self):
        image = self.cleaned_data.get("image")
        required = not (self.instance and self.instance.pk and getattr(self.instance, "image", None))
        return _validate_banner_image(image, required=required)

    def clean_redirect_url(self):
        url = self.cleaned_data.get("redirect_url")
        if url is not None and str(url).strip() == "":
            return None
        return url


# --- Product EDIT: basic fields only (no variant fields on Product) ---
# Includes simple-product base fields; variants remain the source of truth
# whenever they exist for a given product.
BASIC_EDIT_FIELDS = [
    "category",
    "name",
    "slug",
    "description",
    "brand",
    # Simple product base fields (used only when product has no variants)
    "base_price",
    "base_stock",
    "is_featured",
    "is_bestseller",
    "is_deal_of_day",
    "deal_of_day_start",
    "deal_of_day_end",
    "is_active",
    "is_gst_applicable",
    "gst_percentage",
    "hsn_code",
]


class ProductBasicEditForm(forms.ModelForm):
    """Form for POST /admin/products/create-basic/ and update-basic/. No images, no variants."""
    class Meta:
        model = Product
        fields = BASIC_EDIT_FIELDS
        widgets = {
            "category": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Product Name"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "product-slug"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "brand": forms.TextInput(attrs={"class": "form-control", "placeholder": "Brand"}),
            "base_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                    "id": "basic-base_price",
                }
            ),
            "base_stock": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "0",
                    "id": "basic-base_stock",
                }
            ),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_bestseller": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_deal_of_day": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "deal_of_day_start": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "deal_of_day_end": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_gst_applicable": forms.CheckboxInput(attrs={"class": "form-check-input", "id": "basic-is_gst_applicable"}),
            "gst_percentage": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0–28", "min": 0, "max": 28, "step": "0.01"}),
            "hsn_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 8517", "maxlength": 20}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["description"].required = False
        self.fields["brand"].required = False
        self.fields["deal_of_day_start"].required = False
        self.fields["deal_of_day_end"].required = False
        self.fields["gst_percentage"].required = False
        self.fields["hsn_code"].required = False
        active = Category.objects.filter(is_active=True)
        if self.instance and self.instance.pk and self.instance.category_id:
            current = self.instance.category
            if current and not current.is_active:
                active = active | Category.objects.filter(pk=current.pk)
        self.fields["category"].queryset = active.order_by("name")

    def clean(self):
        cleaned = super().clean()
        is_gst = cleaned.get("is_gst_applicable")
        gst_pct = cleaned.get("gst_percentage")
        if is_gst:
            if gst_pct is None:
                self.add_error("gst_percentage", "GST % is required when GST is applicable.")
            else:
                try:
                    pct = float(gst_pct)
                    if pct < 0 or pct > 28:
                        self.add_error("gst_percentage", "GST % must be between 0 and 28.")
                except (TypeError, ValueError):
                    self.add_error("gst_percentage", "Enter a valid number.")
        else:
            if gst_pct is not None:
                cleaned["gst_percentage"] = None
        return cleaned
