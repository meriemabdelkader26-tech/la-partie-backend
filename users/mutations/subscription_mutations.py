from datetime import timedelta

import graphene
from django.conf import settings
from django.utils import timezone
from graphql import GraphQLError

try:
    import stripe
except ImportError:
    stripe = None

from users.billing import get_or_create_user_subscription, has_paid_access
from users.models import SubscriptionPlan, SubscriptionStatus
from users.utils import normalize_role


class PlatformCheckoutSessionType(graphene.ObjectType):
    session_id = graphene.String(required=True)
    checkout_url = graphene.String(required=True)


class BillingPortalSessionType(graphene.ObjectType):
    portal_url = graphene.String(required=True)


def _get_role_price_id(role: str, plan: str) -> str:
    role_price_map = {
        'COMPANY': {
            SubscriptionPlan.PLUS: settings.STRIPE_PRICE_COMPANY_PLUS,
            SubscriptionPlan.PRO: settings.STRIPE_PRICE_COMPANY_PRO,
        },
        'INFLUENCER': {
            SubscriptionPlan.PLUS: settings.STRIPE_PRICE_INFLUENCER_PLUS,
            SubscriptionPlan.PRO: settings.STRIPE_PRICE_INFLUENCER_PRO,
        },
    }

    return role_price_map.get(role, {}).get(plan, '')


def _role_redirect_urls(role: str):
    base = settings.FRONTEND_URL.rstrip('/')
    if role == 'COMPANY':
        success_url = f"{base}/company/campaigns/new?upgrade=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base}/company/campaigns/new?upgrade=cancel"
        return_url = f"{base}/company/campaigns/new"
    elif role == 'INFLUENCER':
        success_url = f"{base}/influencer/campaigns?upgrade=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base}/influencer/campaigns?upgrade=cancel"
        return_url = f"{base}/influencer/campaigns"
    else:
        success_url = f"{base}/?upgrade=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base}/?upgrade=cancel"
        return_url = f"{base}/"

    return success_url, cancel_url, return_url


class CreatePlatformSubscriptionCheckoutSession(graphene.Mutation):
    class Arguments:
        plan = graphene.String(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    checkout = graphene.Field(PlatformCheckoutSessionType)

    def mutate(self, info, plan):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        role = normalize_role(getattr(user, 'role', ''))
        if role not in {'COMPANY', 'INFLUENCER'}:
            raise GraphQLError("Only company and influencer accounts can subscribe.")

        normalized_plan = (plan or '').strip().upper()
        if normalized_plan not in {SubscriptionPlan.PLUS, SubscriptionPlan.PRO}:
            raise GraphQLError("Invalid plan. Supported plans are PLUS and PRO.")

        subscription = get_or_create_user_subscription(user)
        if subscription.plan == normalized_plan and has_paid_access(subscription):
            return CreatePlatformSubscriptionCheckoutSession(
                ok=True,
                message=f"Your {normalized_plan.title()} subscription is already active.",
                checkout=None,
            )

        if settings.STRIPE_SIMULATION_MODE:
            now = timezone.now()
            subscription.plan = normalized_plan
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=30)
            subscription.cancel_at_period_end = False
            subscription.save(
                update_fields=[
                    'plan',
                    'status',
                    'current_period_start',
                    'current_period_end',
                    'cancel_at_period_end',
                    'updated_at',
                ]
            )

            success_url, _, _ = _role_redirect_urls(role)
            simulated_session_id = f"sim_sub_{user.id}_{int(now.timestamp())}"
            checkout_url = success_url.replace('{CHECKOUT_SESSION_ID}', simulated_session_id)
            return CreatePlatformSubscriptionCheckoutSession(
                ok=True,
                message="Simulation mode: subscription upgraded instantly.",
                checkout=PlatformCheckoutSessionType(
                    session_id=simulated_session_id,
                    checkout_url=checkout_url,
                ),
            )

        if stripe is None:
            raise GraphQLError("Stripe SDK is not installed on the server.")

        if not settings.STRIPE_SECRET_KEY:
            raise GraphQLError("Stripe is not configured on the server.")

        price_id = _get_role_price_id(role, normalized_plan)
        if not price_id:
            raise GraphQLError(
                f"Stripe price is not configured for {role} {normalized_plan}."
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        customer_id = subscription.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={
                    'user_id': str(user.id),
                    'role': role,
                },
            )
            customer_id = customer.id
            subscription.stripe_customer_id = customer_id

        success_url, cancel_url, _ = _role_redirect_urls(role)

        checkout_session = stripe.checkout.Session.create(
            mode='subscription',
            customer=customer_id,
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                }
            ],
            allow_promotion_codes=True,
            client_reference_id=str(user.id),
            metadata={
                'billing_purpose': 'platform_subscription',
                'user_id': str(user.id),
                'role': role,
                'target_plan': normalized_plan,
            },
            subscription_data={
                'metadata': {
                    'billing_purpose': 'platform_subscription',
                    'user_id': str(user.id),
                    'role': role,
                    'target_plan': normalized_plan,
                }
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )

        subscription.stripe_price_id = price_id
        subscription.save(update_fields=['stripe_customer_id', 'stripe_price_id', 'updated_at'])

        return CreatePlatformSubscriptionCheckoutSession(
            ok=True,
            message='Checkout session created successfully.',
            checkout=PlatformCheckoutSessionType(
                session_id=checkout_session.id,
                checkout_url=checkout_session.url,
            ),
        )


class CreateBillingPortalSession(graphene.Mutation):
    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    portal = graphene.Field(BillingPortalSessionType)

    def mutate(self, info):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        role = normalize_role(getattr(user, 'role', ''))
        subscription = get_or_create_user_subscription(user)

        _, _, return_url = _role_redirect_urls(role)

        if settings.STRIPE_SIMULATION_MODE:
            simulated_url = f"{return_url}?billing=portal"
            return CreateBillingPortalSession(
                ok=True,
                message='Simulation mode: returning mock billing portal URL.',
                portal=BillingPortalSessionType(portal_url=simulated_url),
            )

        if stripe is None:
            raise GraphQLError("Stripe SDK is not installed on the server.")

        if not settings.STRIPE_SECRET_KEY:
            raise GraphQLError("Stripe is not configured on the server.")

        if not subscription.stripe_customer_id:
            raise GraphQLError("No Stripe customer found for this account.")

        stripe.api_key = settings.STRIPE_SECRET_KEY

        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )

        return CreateBillingPortalSession(
            ok=True,
            message='Billing portal session created successfully.',
            portal=BillingPortalSessionType(portal_url=portal_session.url),
        )
