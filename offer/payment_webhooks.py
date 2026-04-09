import json
from datetime import datetime, timezone as dt_timezone

try:
    import stripe
except ImportError:
    stripe = None
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model

from offer.models import ApplicationStatus, OfferApplication, PaymentStatus
from users.models import SubscriptionPlan, SubscriptionStatus, UserSubscription
from users.utils import normalize_role


User = get_user_model()


STRIPE_STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.TRIALING,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "unpaid": SubscriptionStatus.UNPAID,
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.INCOMPLETE,
}


def _to_datetime(timestamp):
    if not timestamp:
        return None

    try:
        return datetime.fromtimestamp(int(timestamp), tz=dt_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _plan_from_price(role, price_id):
    if not price_id:
        return None

    role = normalize_role(role or "")
    role_price_map = {
        "COMPANY": {
            settings.STRIPE_PRICE_COMPANY_PLUS: SubscriptionPlan.PLUS,
            settings.STRIPE_PRICE_COMPANY_PRO: SubscriptionPlan.PRO,
        },
        "INFLUENCER": {
            settings.STRIPE_PRICE_INFLUENCER_PLUS: SubscriptionPlan.PLUS,
            settings.STRIPE_PRICE_INFLUENCER_PRO: SubscriptionPlan.PRO,
        },
    }

    return role_price_map.get(role, {}).get(price_id)


def _resolve_user_subscription(subscription_payload, metadata=None):
    metadata = metadata or {}
    stripe_subscription_id = subscription_payload.get("id")
    stripe_customer_id = subscription_payload.get("customer")

    user_subscription = None

    if stripe_subscription_id:
        user_subscription = UserSubscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).select_related("user").first()

    if not user_subscription and stripe_customer_id:
        user_subscription = UserSubscription.objects.filter(
            stripe_customer_id=stripe_customer_id
        ).select_related("user").first()

    if not user_subscription:
        user_id = metadata.get("user_id")
        if user_id:
            try:
                user = User.objects.get(id=int(user_id))
                user_subscription, _ = UserSubscription.objects.get_or_create(user=user)
            except (ValueError, User.DoesNotExist):
                return None

    return user_subscription


def _apply_subscription_payload(user_subscription, subscription_payload, fallback_plan=None):
    metadata = subscription_payload.get("metadata") or {}
    role = normalize_role(metadata.get("role") or getattr(user_subscription.user, "role", ""))
    target_plan = (metadata.get("target_plan") or "").upper()

    items = (subscription_payload.get("items") or {}).get("data") or []
    first_item = items[0] if items else {}
    price_id = (first_item.get("price") or {}).get("id")

    if target_plan not in {SubscriptionPlan.PLUS, SubscriptionPlan.PRO}:
        target_plan = _plan_from_price(role, price_id)

    if target_plan not in {SubscriptionPlan.PLUS, SubscriptionPlan.PRO}:
        target_plan = fallback_plan or user_subscription.plan

    stripe_status = STRIPE_STATUS_MAP.get(
        subscription_payload.get("status", ""),
        SubscriptionStatus.INACTIVE,
    )

    user_subscription.plan = target_plan
    user_subscription.status = stripe_status
    user_subscription.stripe_subscription_id = subscription_payload.get("id") or user_subscription.stripe_subscription_id
    user_subscription.stripe_customer_id = subscription_payload.get("customer") or user_subscription.stripe_customer_id
    user_subscription.stripe_price_id = price_id or user_subscription.stripe_price_id
    user_subscription.current_period_start = _to_datetime(subscription_payload.get("current_period_start"))
    user_subscription.current_period_end = _to_datetime(subscription_payload.get("current_period_end"))
    user_subscription.cancel_at_period_end = bool(subscription_payload.get("cancel_at_period_end", False))
    user_subscription.save()


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    if stripe is None:
        return JsonResponse({"detail": "Stripe SDK is not installed on the server."}, status=500)

    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        return JsonResponse({"detail": "Stripe webhook is not configured."}, status=500)

    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, json.JSONDecodeError):
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    event_type = event.get("type")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}
        application_id = metadata.get("application_id")
        billing_purpose = metadata.get("billing_purpose")

        if application_id:
            try:
                application = OfferApplication.objects.select_related("offer").get(id=int(application_id))
            except (ValueError, OfferApplication.DoesNotExist):
                return HttpResponse(status=200)

            if application.status == ApplicationStatus.APPROVED and application.payment_status == PaymentStatus.UNPAID:
                application.payment_status = PaymentStatus.IN_ESCROW
                application.payment_reference = session.get("id")
                application.paid_at = timezone.now()
                application.save(update_fields=["payment_status", "payment_reference", "paid_at", "updated_at"])

        elif billing_purpose == "platform_subscription":
            user_id = metadata.get("user_id") or session.get("client_reference_id")
            target_plan = (metadata.get("target_plan") or "").upper()

            if user_id and target_plan in {SubscriptionPlan.PLUS, SubscriptionPlan.PRO}:
                try:
                    user = User.objects.get(id=int(user_id))
                except (ValueError, User.DoesNotExist):
                    return HttpResponse(status=200)

                user_subscription, _ = UserSubscription.objects.get_or_create(user=user)
                user_subscription.plan = target_plan
                user_subscription.status = SubscriptionStatus.ACTIVE
                user_subscription.stripe_customer_id = session.get("customer") or user_subscription.stripe_customer_id
                user_subscription.stripe_subscription_id = session.get("subscription") or user_subscription.stripe_subscription_id
                user_subscription.cancel_at_period_end = False

                stripe_subscription_id = session.get("subscription")
                if stripe_subscription_id:
                    try:
                        stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
                        _apply_subscription_payload(
                            user_subscription,
                            stripe_subscription,
                            fallback_plan=target_plan,
                        )
                    except Exception:
                        user_subscription.save()
                else:
                    user_subscription.save()

    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        subscription_payload = event["data"]["object"]
        metadata = subscription_payload.get("metadata") or {}

        user_subscription = _resolve_user_subscription(subscription_payload, metadata=metadata)
        if not user_subscription:
            return HttpResponse(status=200)

        if event_type == "customer.subscription.deleted":
            user_subscription.plan = SubscriptionPlan.FREE
            user_subscription.status = SubscriptionStatus.CANCELED
            user_subscription.stripe_subscription_id = subscription_payload.get("id") or user_subscription.stripe_subscription_id
            user_subscription.current_period_end = timezone.now()
            user_subscription.cancel_at_period_end = True
            user_subscription.save()
        else:
            _apply_subscription_payload(user_subscription, subscription_payload)

    return HttpResponse(status=200)
