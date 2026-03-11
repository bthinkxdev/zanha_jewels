import json
import logging

from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Shipment, Order
from .delivery_utils import delivery_enabled

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class ShiprocketWebhookView(View):
    """
    Handle Shiprocket webhooks.

    Expected responsibilities:
      - Validate request (optional token header)
      - Find Shipment by AWB or order_id
      - Update current_status + tracking_data
      - Update Order.status for delivered / RTO / cancelled events
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            # If delivery integration is disabled, ignore incoming webhooks gracefully.
            if not delivery_enabled():
                return JsonResponse({"error": "Delivery integration disabled"}, status=403)
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                return HttpResponseBadRequest("Invalid JSON")

            # Optional simple token validation
            expected_token = getattr(settings, "SHIPROCKET_WEBHOOK_TOKEN", None)
            if expected_token:
                token = request.headers.get("X-Shiprocket-Token") or request.GET.get("token")
                if token != expected_token:
                    return JsonResponse({"error": "Unauthorized"}, status=403)

            awb = (
                payload.get("awb")
                or payload.get("awb_code")
                or payload.get("AWB")
                or payload.get("shipment_awb")
            )
            order_ref = payload.get("order_id") or payload.get("order_number")

            shipment = None
            if awb:
                shipment = Shipment.objects.select_related("order").filter(awb_code=awb).first()
            if not shipment and order_ref:
                shipment = (
                    Shipment.objects.select_related("order")
                    .filter(order__order_number=str(order_ref))
                    .first()
                )

            if not shipment:
                logger.warning("Shiprocket webhook: shipment not found for payload %s", payload)
                return JsonResponse({"error": "Shipment not found"}, status=404)

            # Normalize status and tracking details
            raw_status = (
                payload.get("current_status")
                or payload.get("status")
                or payload.get("courier_status")
                or ""
            )
            normalized_status = str(raw_status)
            activities = payload.get("activities") or payload.get("tracking_history") or []
            eta = payload.get("etd") or payload.get("estimated_delivery_date") or ""

            tracking = {
                "status": normalized_status,
                "awb_code": awb or shipment.awb_code,
                "order_id": order_ref or shipment.order.order_number,
                "activities": activities,
                "eta": eta,
                "raw": payload,
            }

            shipment.current_status = normalized_status or shipment.current_status
            shipment.tracking_data = tracking
            shipment.save(update_fields=["current_status", "tracking_data", "updated_at"])

            # Update order status based on shipment status semantics
            order = shipment.order
            status_lc = (normalized_status or "").lower()

            if "delivered" in status_lc:
                order.status = Order.Status.DELIVERED
                order.save(update_fields=["status", "updated_at"])
            elif "rto" in status_lc or "return" in status_lc:
                order.status = Order.Status.CANCELLED
                order.save(update_fields=["status", "updated_at"])
            elif "cancelled" in status_lc and order.status != Order.Status.DELIVERED:
                order.status = Order.Status.CANCELLED
                order.save(update_fields=["status", "updated_at"])

            return JsonResponse({"success": True})
        except Exception as exc:
            logger.error("Error handling Shiprocket webhook: %s", exc, exc_info=True)
            return JsonResponse({"error": "Internal error"}, status=500)

