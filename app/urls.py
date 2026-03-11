from django.urls import path

from . import views
from .webhook_views import ShiprocketWebhookView

app_name = "store"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("api/new-arrivals/", views.NewArrivalsView.as_view(), name="api_new_arrivals"),
    path("api/top-selling/", views.TopSellingView.as_view(), name="api_top_selling"),
    path("api/recently-viewed/", views.RecentlyViewedView.as_view(), name="api_recently_viewed"),
    path("api/you-may-like/", views.YouMayLikeView.as_view(), name="api_you_may_like"),
    path("products/", views.ProductListView.as_view(), name="product_list"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="product_detail"),
    path("api/products/<int:product_id>/reviews/", views.ProductReviewCreateView.as_view(), name="product_review_create"),
    path("products/color-images/", views.ProductColorImagesView.as_view(), name="product_color_images"),
    path("api/products/variant-resolve/", views.ProductVariantResolveView.as_view(), name="product_variant_resolve"),
    path("cart/", views.CartView.as_view(), name="cart"),
    path("cart/add/", views.AddToCartView.as_view(), name="cart_add"),
    path("cart/buy-now/", views.BuyNowView.as_view(), name="buy_now"),
    path("cart/update/", views.UpdateCartItemView.as_view(), name="cart_update"),
    path("cart/remove/<int:item_id>/", views.RemoveCartItemView.as_view(), name="cart_remove"),
    path("api/wishlist/toggle/", views.WishlistToggleView.as_view(), name="wishlist_toggle"),
    path("api/wishlist/remove/", views.RemoveFromWishlistView.as_view(), name="wishlist_remove"),
    path("api/wishlist/ids/", views.WishlistIdsView.as_view(), name="wishlist_ids"),
    path("wishlist/", views.WishlistPageView.as_view(), name="wishlist"),
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("checkout/place-order/", views.OrderCreateView.as_view(), name="order_create"),
    path("checkout/create-razorpay-order/", views.CreateRazorpayOrderView.as_view(), name="create_razorpay_order"),
    path("orders/<slug:order_number>/", views.OrderSuccessView.as_view(), name="order_success"),
    path("orders/<slug:order_number>/detail/", views.OrderDetailPageView.as_view(), name="order_detail"),
    path("orders/", views.OrderHistoryView.as_view(), name="order_history"),
    path("payment/razorpay/verify/", views.RazorpayPaymentVerifyView.as_view(), name="razorpay_verify"),
    path("payment/razorpay/cancel/", views.RazorpayPaymentCancelView.as_view(), name="razorpay_cancel"),
    path("about/", views.StaticPageView.as_view(template_name="about.html", extra_context={"active_page": "about"}), name="about"),
    path("contact/", views.ContactView.as_view(), name="contact"),
    path("newsletter/subscribe/", views.NewsletterSubscribeView.as_view(), name="newsletter_subscribe"),
    path("privacy/", views.StaticPageView.as_view(template_name="privacy.html", extra_context={"active_page": "privacy"}), name="privacy"),
    path("terms/", views.StaticPageView.as_view(template_name="terms.html", extra_context={"active_page": "terms"}), name="terms"),
    path("shipping/", views.StaticPageView.as_view(template_name="shipping.html", extra_context={"active_page": "shipping"}), name="shipping"),
    path("webhooks/shiprocket/", ShiprocketWebhookView.as_view(), name="shiprocket_webhook"),
    path('api/cart/drawer/', views.CartDrawerView.as_view(), name='cart_drawer'),
]

