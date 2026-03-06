"""
Audit Variant and VariantImage data integrity.

Run: python manage.py audit_variant_integrity

Checks:
- VariantImage: valid variant_id (FK), no orphans.
- Variant: no negative stock, no duplicate SKU (per product allowed; global unique).
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from app.models import Variant, VariantImage


class Command(BaseCommand):
    help = "Audit variant and image integrity: orphans, negative stock, duplicate SKU."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Reserved for future use.",
        )

    def handle(self, *args, **options):
        errors = []
        # 1) VariantImage with missing variant (CASCADE should prevent)
        variant_ids = set(Variant.objects.values_list("pk", flat=True))
        orphan_images = VariantImage.objects.exclude(variant_id__in=variant_ids)
        if orphan_images.exists():
            errors.append(f"VariantImage with missing variant: {orphan_images.count()}")

        # 2) Variant with negative stock (DB constraint should prevent)
        neg_stock = Variant.objects.filter(stock_quantity__lt=0)
        if neg_stock.exists():
            errors.append(f"Variant with negative stock: {neg_stock.count()}")

        # 3) Duplicate non-empty SKU (Variant.sku is unique globally)
        dup_sku = (
            Variant.objects.exclude(sku__isnull=True).exclude(sku="").values("sku").annotate(cnt=Count("id")).filter(cnt__gt=1)
        if dup_sku:
            errors.append(f"Duplicate SKU: {list(dup_sku)}")

        if errors:
            self.stderr.write(self.style.ERROR("Integrity issues found:"))
            for e in errors:
                self.stderr.write(self.style.ERROR(f"  - {e}"))
            return
        self.stdout.write(self.style.SUCCESS("Audit passed: no orphan images, no negative stock, no duplicate SKU."))
