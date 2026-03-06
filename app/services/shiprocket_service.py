import logging
import time
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from ..models import Order, Shipment
from .parcel_calculator import calculate_parcel

logger = logging.getLogger(__name__)


class ShiprocketAPIError(Exception):
    """Wrapped errors from Shiprocket API or network layer."""


class ShiprocketService:
    """
    Shiprocket API client with basic retry logic and structured logging.
    """

    def __init__(self, base_url: Optional[str] = None, max_retries: int = 3, timeout: int = 15):
        self.base_url = base_url or getattr(
            settings,
            "SHIPROCKET_BASE_URL",
            "https://apiv2.shiprocket.in/v1/external",
        )
        self.max_retries = max_retries
        self.timeout = timeout

    # ---------- Core HTTP helpers ----------

    def authenticate(self) -> str:
        """
        Return JWT token (cached). Expires in ~10 days; cached for 9.
        """
        cache_key = "shiprocket_token"
        token = cache.get(cache_key)
        if token:
            return token

        try:
            response = requests.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": settings.SHIPROCKET_EMAIL,
                    "password": settings.SHIPROCKET_PASSWORD,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("token")
            if not token:
                raise ShiprocketAPIError("Shiprocket auth response missing token.")
            cache.set(cache_key, token, timeout=60 * 60 * 24 * 9)
            return token
        except requests.RequestException as exc:
            logger.error("Shiprocket auth failed: %s", exc, exc_info=True)
            raise ShiprocketAPIError(f"Shiprocket auth failed: {exc}") from exc

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authenticate()}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, *, json=None, params=None, timeout=None):
        url = f"{self.base_url}{path}"
        timeout = timeout or self.timeout
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Shiprocket %s %s attempt %s", method, path, attempt)
                response = requests.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=self._headers(),
                    timeout=timeout,
                )
                if 500 <= response.status_code < 600:
                    # Server-side error, allow retry
                    logger.warning(
                        "Shiprocket %s %s server error %s: %s",
                        method,
                        path,
                        response.status_code,
                        response.text[:500],
                    )
                    last_exc = ShiprocketAPIError(
                        f"Shiprocket server error {response.status_code}"
                    )
                else:
                    response.raise_for_status()
                    return response.json()
            except requests.RequestException as exc:
                # Network or HTTP error
                logger.warning(
                    "Shiprocket %s %s request error on attempt %s: %s",
                    method,
                    path,
                    attempt,
                    exc,
                    exc_info=True,
                )
                last_exc = exc

            # Backoff before retry, except after last attempt
            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 5))

        raise ShiprocketAPIError(f"Shiprocket request failed for {path}: {last_exc}")

    # ---------- Public API methods ----------

    def create_order(self, order: Order, shipment: Shipment) -> dict:
        """
        Create Shiprocket order for given Order using calculated parcel dimensions.
        """
        if not order.address:
            raise ShiprocketAPIError("Order has no shipping address.")

        parcel = calculate_parcel(order)
        address = order.address
        items = order.items.select_related("product", "selected_variant").all()

        order_items = []
        for item in items:
            variant = item.selected_variant
            sku = getattr(variant, "sku", None) or f"SKU-{getattr(variant, 'id', '')}"
            order_items.append(
                {
                    "name": item.product_name,
                    "sku": sku,
                    "units": int(item.quantity),
                    "selling_price": str(item.unit_price),
                }
            )

        payment_method = "Prepaid"
        try:
            payment = getattr(order, "payment", None)
            if payment and getattr(payment, "method", "") == "cod":
                payment_method = "COD"
        except Exception:
            pass

        payload = {
            "order_id": str(order.order_number),
            "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
            "pickup_location": getattr(settings, "SHIPROCKET_PICKUP_LOCATION", "Primary"),
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
            "order_items": order_items,
            "payment_method": payment_method,
            "sub_total": str(order.subtotal),
            "length": float(parcel["length"]),
            "breadth": float(parcel["breadth"]),
            "height": float(parcel["height"]),
            "weight": float(parcel["weight"]),
        }

        data = self._request("POST", "/orders/create/adhoc", json=payload)
        logger.info("Shiprocket create_order success for %s: %s", order.order_number, data)
        return data

    def assign_awb(self, shipment: Shipment) -> dict:
        if not shipment.shiprocket_shipment_id:
            raise ShiprocketAPIError("Shipment has no Shiprocket shipment_id.")
        payload = {"shipment_id": shipment.shiprocket_shipment_id}
        data = self._request("POST", "/courier/assign/awb", json=payload)
        logger.info(
            "Shiprocket assign_awb success for order %s: %s",
            shipment.order.order_number,
            data,
        )
        return data

    def request_pickup(self, shipment: Shipment) -> dict:
        if not shipment.shiprocket_shipment_id:
            raise ShiprocketAPIError("Shipment has no Shiprocket shipment_id.")
        payload = {"shipment_id": [shipment.shiprocket_shipment_id]}
        data = self._request("POST", "/courier/generate/pickup", json=payload)
        logger.info(
            "Shiprocket request_pickup success for order %s: %s",
            shipment.order.order_number,
            data,
        )
        return data

    def generate_label(self, shipment: Shipment) -> dict:
        if not shipment.shiprocket_shipment_id:
            raise ShiprocketAPIError("Shipment has no Shiprocket shipment_id.")
        payload = {"shipment_id": [shipment.shiprocket_shipment_id]}
        data = self._request("POST", "/courier/generate/label", json=payload)
        logger.info(
            "Shiprocket generate_label success for order %s: %s",
            shipment.order.order_number,
            data,
        )
        return data

    def cancel_shipment(self, shipment: Shipment) -> dict:
        """
        Attempt to cancel a shipment in Shiprocket.
        The exact endpoint/payload may need adjustment per Shiprocket docs.
        """
        if not shipment.shiprocket_shipment_id and not shipment.shiprocket_order_id:
            raise ShiprocketAPIError("Shipment has no Shiprocket identifiers to cancel.")

        payload = {}
        if shipment.shiprocket_shipment_id:
            payload["shipment_id"] = [shipment.shiprocket_shipment_id]
        if shipment.shiprocket_order_id:
            payload["ids"] = [shipment.shiprocket_order_id]

        data = self._request("POST", "/orders/cancel", json=payload)
        logger.info(
            "Shiprocket cancel_shipment success for order %s: %s",
            shipment.order.order_number,
            data,
        )
        return data

    def track_shipment(self, awb_code: str) -> dict:
        path = f"/courier/track/awb/{awb_code}"
        data = self._request("GET", path)
        logger.info("Shiprocket track_shipment success for AWB %s", awb_code)
        return data


shiprocket_service = ShiprocketService()


def create_shipment_for_order(order: Order, shipment: Optional[Shipment] = None) -> Shipment:
    """
    Orchestrate full shipment creation for an order:
      - create Shiprocket order
      - assign AWB
      - request pickup
      - generate label
      - update Shipment + Order.status

    Raises ShiprocketAPIError on failure.
    """
    if shipment is None:
        shipment = Shipment.objects.create(order=order, current_status="pending_creation")

    try:
        # 1) Create order in Shiprocket
        create_data = shiprocket_service.create_order(order, shipment)
        shipment.shiprocket_order_id = str(create_data.get("order_id") or "")
        shipment.shiprocket_shipment_id = str(create_data.get("shipment_id") or "")
        shipment.current_status = "created"
        shipment.save(
            update_fields=[
                "shiprocket_order_id",
                "shiprocket_shipment_id",
                "current_status",
                "updated_at",
            ]
        )

        # 2) Assign courier + AWB
        awb_data = shiprocket_service.assign_awb(shipment)
        awb_response = awb_data.get("response", {}) or awb_data
        awb_inner = awb_response.get("data", {}) or awb_response
        awb_code = awb_inner.get("awb_code") or awb_inner.get("awb") or ""
        courier_name = awb_inner.get("courier_name") or ""
        shipment.awb_code = str(awb_code)
        shipment.courier_name = str(courier_name)
        shipment.current_status = "awb_assigned"
        shipment.save(
            update_fields=["awb_code", "courier_name", "current_status", "updated_at"]
        )

        # 3) Request pickup
        shiprocket_service.request_pickup(shipment)
        shipment.current_status = "pickup_scheduled"
        shipment.save(update_fields=["current_status", "updated_at"])

        # 4) Generate label
        label_data = shiprocket_service.generate_label(shipment)
        label_url = (
            label_data.get("label_url")
            or label_data.get("response", {}).get("data", {}).get("label_url", "")
        )
        shipment.label_url = label_url
        shipment.current_status = "label_generated"
        shipment.save(update_fields=["label_url", "current_status", "updated_at"])

        # Mark order as shipped after successful creation
        if order.status == Order.Status.CONFIRMED:
            order.status = Order.Status.SHIPPED
            order.save(update_fields=["status", "updated_at"])

        return shipment
    except ShiprocketAPIError:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error while creating shipment for order %s: %s",
            order.order_number,
            exc,
            exc_info=True,
        )
        raise ShiprocketAPIError(str(exc)) from exc

