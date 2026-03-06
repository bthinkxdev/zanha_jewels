import requests
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

SHIPROCKET_BASE_URL = "https://apiv2.shiprocket.in/v1/external"


class ShiprocketService:

    def get_token(self):
        """Get JWT token - cached for 9 days (expires in 10)"""
        token = cache.get("shiprocket_token")
        if token:
            return token

        response = requests.post(
            f"{SHIPROCKET_BASE_URL}/auth/login",
            json={
                "email": settings.SHIPROCKET_EMAIL,
                "password": settings.SHIPROCKET_PASSWORD,
            },
            timeout=10,
        )
        response.raise_for_status()
        token = response.json()["token"]
        cache.set("shiprocket_token", token, timeout=60 * 60 * 24 * 9)
        return token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json",
        }

    def create_order(self, order):
        """
        Create shipment order on Shiprocket.
        order = your Order model instance
        """
        address = order.address
        items = order.items.select_related("product", "selected_variant").all()

        payload = {
            "order_id": str(order.order_number),
            "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
            "pickup_location": "Primary",  # Must match name in Shiprocket dashboard

            # Billing info from your Address model
            "billing_customer_name": address.full_name,
            "billing_last_name": "",
            "billing_address": address.address_line,
            "billing_city": address.city,
            "billing_pincode": address.pincode,
            "billing_state": address.state,
            "billing_country": "India",
            "billing_email": address.email or "",
            "billing_phone": address.phone,

            "shipping_is_billing": True,

            # Order items from your OrderItem model
            "order_items": [
                {
                    "name": item.product_name,
                    "sku": item.selected_variant.sku or f"SKU-{item.selected_variant.id}",
                    "units": item.quantity,
                    "selling_price": str(item.unit_price),
                }
                for item in items
            ],

            # COD if payment method is cod, else Prepaid
            "payment_method": "COD" if hasattr(order, 'payment') and order.payment.method == "cod" else "Prepaid",
            "sub_total": str(order.subtotal),

            # Default dimensions — update these with real product dimensions later
            "length": 10,
            "breadth": 10,
            "height": 10,
            "weight": 0.5,
        }

        response = requests.post(
            f"{SHIPROCKET_BASE_URL}/orders/create/adhoc",
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def generate_awb(self, shipment_id):
        """Assign courier and generate AWB tracking number"""
        response = requests.post(
            f"{SHIPROCKET_BASE_URL}/courier/assign/awb",
            json={"shipment_id": shipment_id},
            headers=self._headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def request_pickup(self, shipment_id):
        """Schedule pickup from your warehouse"""
        response = requests.post(
            f"{SHIPROCKET_BASE_URL}/courier/generate/pickup",
            json={"shipment_id": [shipment_id]},
            headers=self._headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def get_label(self, shipment_id):
        """Get printable shipping label PDF URL"""
        response = requests.post(
            f"{SHIPROCKET_BASE_URL}/courier/generate/label",
            json={"shipment_id": [shipment_id]},
            headers=self._headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def track_shipment(self, awb_code):
        """Track shipment by AWB code"""
        response = requests.get(
            f"{SHIPROCKET_BASE_URL}/courier/track/awb/{awb_code}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def track_by_order_id(self, order_number):
        """Track shipment by your order number"""
        response = requests.get(
            f"{SHIPROCKET_BASE_URL}/courier/track?order_id={order_number}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


# Singleton instance — import this everywhere
shiprocket = ShiprocketService()