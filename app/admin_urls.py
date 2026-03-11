from django.urls import path

from . import admin_views
from . import admin_report_views

app_name = "admin_panel"

urlpatterns = [
    # Authentication
    path("login/", admin_views.AdminLoginView.as_view(), name="login"),
    path("logout/", admin_views.AdminLogoutView.as_view(), name="logout"),

    # Dashboard
    path("", admin_views.AdminDashboardView.as_view(), name="dashboard"),

    # Reports
    path("reports/", admin_report_views.ReportsDashboardView.as_view(), name="report_list"),
    path("reports/orders/", admin_report_views.OrdersReportView.as_view(), name="report_orders"),
    path("reports/sales/", admin_report_views.SalesReportView.as_view(), name="report_sales"),
    path("reports/products/", admin_report_views.ProductPerformanceReportView.as_view(), name="report_products"),
    path("reports/customers/", admin_report_views.CustomerReportView.as_view(), name="report_customers"),
    path("reports/inventory/", admin_report_views.InventoryReportView.as_view(), name="report_inventory"),
    path("reports/api/<str:report_type>/", admin_report_views.ReportApiView.as_view(), name="report_api"),
    path("reports/export/<str:report_type>/<str:format_type>/", admin_report_views.ReportExportView.as_view(), name="report_export"),

    # Banners
    path("banners/", admin_views.BannerListView.as_view(), name="banner_list"),
    path("banners/create/", admin_views.BannerCreateView.as_view(), name="banner_create"),
    path("banners/<int:pk>/edit/", admin_views.BannerUpdateView.as_view(), name="banner_edit"),
    path("banners/<int:pk>/delete/", admin_views.BannerDeleteView.as_view(), name="banner_delete"),

    # Categories
    path("categories/", admin_views.CategoryListView.as_view(), name="category_list"),
    path("categories/create/", admin_views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", admin_views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", admin_views.CategoryDeleteView.as_view(), name="category_delete"),

    # Deals Of The Day
    path("deals/", admin_views.DealOfDayListView.as_view(), name="deal_list"),

    # Products
    path("products/", admin_views.ProductListView.as_view(), name="product_list"),
    path("products/create/", admin_views.ProductCreateView.as_view(), name="product_create"),
    path("products/create-basic/", admin_views.ProductCreateBasicView.as_view(), name="product_create_basic"),
    path("products/<int:pk>/edit/", admin_views.ProductEditView.as_view(), name="product_edit"),
    path("products/<int:pk>/update-basic/", admin_views.ProductUpdateBasicView.as_view(), name="product_update_basic"),
    path("products/<int:pk>/toggle-active/", admin_views.ProductToggleActiveView.as_view(), name="product_toggle_active"),
    path("products/<int:pk>/delete/", admin_views.ProductDeleteView.as_view(), name="product_delete"),
    path("products/<int:pk>/delete-check/", admin_views.ProductDeleteCheckView.as_view(), name="product_delete_check"),

    # Attributes
    path("products/<int:pk>/attributes/", admin_views.ProductAttributesListApiView.as_view(), name="product_attributes_list"),
    path("products/<int:pk>/attributes/add/", admin_views.ProductAttributeCreateApiView.as_view(), name="product_attribute_add"),
    path("products/<int:pk>/attributes/reorder/", admin_views.ProductAttributesReorderApiView.as_view(), name="product_attributes_reorder"),
    path("attributes/<int:attr_id>/update/", admin_views.ProductAttributeUpdateApiView.as_view(), name="attribute_update"),
    path("attributes/<int:attr_id>/delete/", admin_views.ProductAttributeDeleteApiView.as_view(), name="attribute_delete"),
    path("attributes/<int:attr_id>/values/add/", admin_views.ProductAttributeValueCreateApiView.as_view(), name="attribute_value_add"),
    path("attributes/<int:attr_id>/values/reorder/", admin_views.ProductAttributeValuesReorderApiView.as_view(), name="attribute_values_reorder"),
    path("attribute-values/<int:av_id>/update/", admin_views.ProductAttributeValueUpdateApiView.as_view(), name="attribute_value_update"),
    path("attribute-values/<int:av_id>/delete/", admin_views.ProductAttributeValueDeleteApiView.as_view(), name="attribute_value_delete"),

    # Variants
    path("products/<int:pk>/variants/", admin_views.ProductVariantsListApiView.as_view(), name="product_variants_list"),
    path("products/<int:pk>/variants/add/", admin_views.VariantCreateApiView.as_view(), name="variant_add"),
    path("variants/<int:variant_id>/update/", admin_views.VariantUpdateApiView.as_view(), name="variant_update"),
    path("variants/<int:variant_id>/delete/", admin_views.VariantDeleteApiView.as_view(), name="variant_delete"),
    path("variants/<int:variant_id>/upload-image/", admin_views.VariantUploadImageView.as_view(), name="variant_upload_image"),
    path("variant-images/<int:image_id>/delete/", admin_views.VariantImageDeleteView.as_view(), name="variant_image_delete"),
    path("variant-images/<int:image_id>/set-primary/", admin_views.VariantImageSetPrimaryView.as_view(), name="variant_image_set_primary"),
    path("variant-images/reorder/", admin_views.VariantImageReorderView.as_view(), name="variant_image_reorder"),

    # Simple product base images
    path("products/<int:product_id>/base-images/upload/", admin_views.ProductImageUploadView.as_view(), name="product_image_upload"),
    path("products/base-images/<int:image_id>/delete/", admin_views.ProductImageDeleteView.as_view(), name="product_image_delete"),
    path("products/base-images/<int:image_id>/set-primary/", admin_views.ProductImageSetPrimaryView.as_view(), name="product_image_set_primary"),
    path("products/base-images/reorder/", admin_views.ProductImageReorderView.as_view(), name="product_image_reorder"),

    # Orders
    path("orders/", admin_views.OrderListView.as_view(), name="order_list"),
    path("orders/<slug:order_number>/", admin_views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<slug:order_number>/invoice/", admin_views.OrderInvoiceView.as_view(), name="order_invoice"),
    path("orders/<slug:order_number>/update-status/", admin_views.OrderUpdateStatusView.as_view(), name="order_update_status"),
    path("orders/<slug:order_number>/shipment/retry/", admin_views.ShipmentRetryView.as_view(), name="order_shipment_retry"),
    path("orders/<slug:order_number>/shipment/cancel/", admin_views.ShipmentCancelView.as_view(), name="order_shipment_cancel"),
    path("orders/<slug:order_number>/shipment/refresh-tracking/", admin_views.OrderShipmentRefreshTrackingView.as_view(), name="order_shipment_refresh_tracking"),

    # Messages
    path("messages/", admin_views.MessageListView.as_view(), name="message_list"),
    path("messages/<int:pk>/toggle-resolved/", admin_views.MessageToggleResolvedView.as_view(), name="message_toggle_resolved"),

    # File Upload (S3)
    path("upload/s3/", admin_views.S3FileUploadView.as_view(), name="s3_upload"),

    # Reviews
    path("reviews/", admin_views.ReviewListView.as_view(), name="review_list"),
]
