import graphene
from graphene_django import DjangoObjectType
from graphql_relay import from_global_id
from decimal import Decimal, InvalidOperation
import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Sum
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
try:
    import stripe
except ImportError:
    stripe = None
from offer.models import (
    Offer,
    OfferApplication,
    ApplicationStatus,
    PaymentStatus,
    InfluencerPaymentMethod,
    PayoutRequest,
    PaymentMethodType,
    PayoutRequestStatus,
)
from graphql import GraphQLError
from users.utils import check_user_role, safe_create_notification
from users.models import Notification, NotificationType
from users.billing import get_user_quota_snapshot

User = get_user_model()


class OfferApplicationType(DjangoObjectType):
    class Meta:
        model = OfferApplication
        fields = "__all__"


class CheckoutSessionType(graphene.ObjectType):
    session_id = graphene.String(required=True)
    checkout_url = graphene.String(required=True)


def create_checkout_session_via_http(application, amount_cents):
    success_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}"
        "/company/dashboard?payment=success&session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{settings.FRONTEND_URL.rstrip('/')}/company/dashboard?payment=cancelled"

    form_data = [
        ("mode", "payment"),
        ("payment_method_types[]", "card"),
        ("line_items[0][quantity]", "1"),
        ("line_items[0][price_data][currency]", settings.STRIPE_CURRENCY),
        ("line_items[0][price_data][unit_amount]", str(amount_cents)),
        ("line_items[0][price_data][product_data][name]", f"Escrow payment - {application.offer.title}"),
        (
            "line_items[0][price_data][product_data][description]",
            f"Application #{application.id} for {application.user.name or application.user.email}",
        ),
        ("metadata[application_id]", str(application.id)),
        ("metadata[offer_id]", str(application.offer.id)),
        ("metadata[company_user_id]", str(application.offer.created_by_id)),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
    ]

    body = urllib.parse.urlencode(form_data).encode("utf-8")
    request = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=body,
        method="POST",
    )
    request.add_header("Authorization", f"Bearer {settings.STRIPE_SECRET_KEY}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            error_message = error_payload.get("error", {}).get("message")
        except Exception:
            error_message = None
        raise GraphQLError(error_message or "Stripe API request failed.")
    except URLError:
        raise GraphQLError("Unable to reach Stripe API.")

    session_id = payload.get("id")
    checkout_url = payload.get("url")

    if not session_id or not checkout_url:
        raise GraphQLError("Stripe checkout session is invalid.")

    return session_id, checkout_url


def create_checkout_session(application, amount_cents):
    if stripe is not None:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": settings.STRIPE_CURRENCY,
                            "unit_amount": amount_cents,
                            "product_data": {
                                "name": f"Escrow payment - {application.offer.title}",
                                "description": f"Application #{application.id} for {application.user.name or application.user.email}",
                            },
                        },
                    }
                ],
                metadata={
                    "application_id": str(application.id),
                    "offer_id": str(application.offer.id),
                    "company_user_id": str(application.offer.created_by_id),
                },
                success_url=f"{settings.FRONTEND_URL.rstrip('/')}/company/dashboard?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL.rstrip('/')}/company/dashboard?payment=cancelled",
            )
        except Exception:
            raise GraphQLError("Failed to create Stripe Checkout session.")

        return session.id, session.url

    # Fallback when Stripe SDK isn't available in the runtime environment.
    return create_checkout_session_via_http(application, amount_cents)


class InfluencerPaymentMethodType(DjangoObjectType):
    class Meta:
        model = InfluencerPaymentMethod
        fields = "__all__"


class PayoutRequestType(DjangoObjectType):
    class Meta:
        model = PayoutRequest
        fields = "__all__"


class CreateOfferApplication(graphene.Mutation):
    class Arguments:
        offer_id = graphene.ID(required=True)
        proposal = graphene.String(required=True)
        asking_price = graphene.Float(required=True)

    ok = graphene.Boolean()
    application = graphene.Field(OfferApplicationType)

    def mutate(self, info, offer_id, proposal, asking_price):
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        if not (check_user_role(user, "INFLUENCER") or user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("Only influencer accounts can apply to campaigns.")

        try:
            asking_price = Decimal(str(asking_price))
        except (InvalidOperation, ValueError, TypeError):
            raise GraphQLError("Invalid asking price format.")

        quota_snapshot = get_user_quota_snapshot(user)
        if not quota_snapshot.can_apply_to_campaign:
            raise GraphQLError(
                quota_snapshot.application_block_message
                or "Application limit reached. Upgrade to continue."
            )

        # Decode Relay global ID if needed
        try:
            node_type, pk = from_global_id(offer_id)
            if node_type == 'OfferNode':
                offer_id = int(pk)
            else:
                offer_id = int(offer_id)
        except Exception:
            try:
                offer_id = int(offer_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid offer ID format.")

        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            raise GraphQLError("Offer not found.")

        # empêcher double postulation
        if OfferApplication.objects.filter(offer=offer, user=user).exists():
            raise GraphQLError("You already applied to this offer.")

        application = OfferApplication.objects.create(
            offer=offer,
            user=user,
            proposal=proposal,
            asking_price=asking_price
        )

        # Notify the company owner about the new application.
        safe_create_notification(
            user=offer.created_by,
            notification_type=NotificationType.APPLICATION,
            title="New application received",
            message=f"{user.name or user.email} applied to '{offer.title}'.",
            link=f"/company/campaigns/{offer.id}/applications",
            is_read=False,
        )

        # Notify admins for moderation visibility.
        admin_users = User.objects.filter(
            Q(is_staff=True)
            | Q(role='ADMIN')
            | Q(role__iexact='admin')
            | Q(role__icontains='ADMIN')
        ).exclude(id=offer.created_by_id)

        for admin_user in admin_users:
            safe_create_notification(
                user=admin_user,
                notification_type=NotificationType.APPLICATION,
                title="New influencer application",
                message=f"Application submitted for '{offer.title}'.",
                link=f"/admin/offer/detail/{offer.id}",
                is_read=False,
            )

        return CreateOfferApplication(ok=True, application=application)


class DeclineOfferOpportunity(graphene.Mutation):
    class Arguments:
        offer_id = graphene.ID(required=True)
        reason = graphene.String(required=False)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    errors = graphene.List(graphene.String)
    application = graphene.Field(OfferApplicationType)

    def mutate(self, info, offer_id, reason=None):
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        if not (check_user_role(user, "INFLUENCER") or user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("Only influencer accounts can decline opportunities.")

        try:
            node_type, pk = from_global_id(offer_id)
            if node_type == 'OfferNode':
                offer_id = int(pk)
            else:
                offer_id = int(offer_id)
        except Exception:
            try:
                offer_id = int(offer_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid offer ID format.")

        try:
            offer = Offer.objects.select_related("created_by").get(id=offer_id)
        except Offer.DoesNotExist:
            return DeclineOfferOpportunity(
                success=False,
                message="Offer not found.",
                errors=["Offer not found."],
                application=None,
            )

        if offer.created_by_id == user.id:
            return DeclineOfferOpportunity(
                success=False,
                message="You cannot decline your own offer.",
                errors=["You cannot decline your own offer."],
                application=None,
            )

        existing_application = OfferApplication.objects.filter(offer=offer, user=user).first()
        if existing_application:
            if existing_application.status == ApplicationStatus.WITHDRAW:
                return DeclineOfferOpportunity(
                    success=True,
                    message="Opportunity already declined.",
                    errors=[],
                    application=existing_application,
                )

            return DeclineOfferOpportunity(
                success=False,
                message="You already have an application for this offer.",
                errors=["You already have an application for this offer."],
                application=existing_application,
            )

        application = OfferApplication.objects.create(
            offer=offer,
            user=user,
            proposal=(reason or "Opportunity declined by influencer."),
            asking_price=offer.min_budget,
            status=ApplicationStatus.WITHDRAW,
        )

        return DeclineOfferOpportunity(
            success=True,
            message="Opportunity declined successfully.",
            errors=[],
            application=application,
        )
    
class UpdateOfferApplicationStatus(graphene.Mutation):
    class Arguments:
        application_id = graphene.ID(required=True)
        status = graphene.String(required=True)  

    ok = graphene.Boolean()
    application = graphene.Field(OfferApplicationType)

    def mutate(self, info, application_id, status):
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        if status not in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]:
            raise GraphQLError("Invalid status.")

        # Decode Relay global ID if needed
        try:
            node_type, pk = from_global_id(application_id)
            if node_type == 'OfferApplicationNode':
                application_id = int(pk)
            else:
                application_id = int(application_id)
        except Exception:
            try:
                application_id = int(application_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid application ID format.")

        try:
            application = OfferApplication.objects.select_related("offer").get(id=application_id)
        except OfferApplication.DoesNotExist:
            raise GraphQLError("Application not found.")

        # Vérifier que l'utilisateur est bien le créateur de l'offre
        if application.offer.created_by != user:
            raise GraphQLError("You are not allowed to accept/reject this application.")

        application.status = status
        application.save()

        safe_create_notification(
            user=application.user,
            notification_type=NotificationType.APPLICATION,
            title=f"Application {status}",
            message=f"Your application for '{application.offer.title}' is now {status}.",
            link="/influencer/campaigns",
            is_read=False,
        )

        admin_users = User.objects.filter(
            Q(is_staff=True)
            | Q(role='ADMIN')
            | Q(role__iexact='admin')
            | Q(role__icontains='ADMIN')
        ).exclude(id=user.id)

        for admin_user in admin_users:
            safe_create_notification(
                user=admin_user,
                notification_type=NotificationType.APPLICATION,
                title="Application status updated",
                message=f"'{application.offer.title}' application is now {status}.",
                link=f"/admin/offer/detail/{application.offer.id}",
                is_read=False,
            )

        return UpdateOfferApplicationStatus(ok=True, application=application)


class MarkApplicationPaymentEscrow(graphene.Mutation):
    class Arguments:
        application_id = graphene.ID(required=True)
        payment_reference = graphene.String(required=False)

    ok = graphene.Boolean()
    application = graphene.Field(OfferApplicationType)

    def mutate(self, info, application_id, payment_reference=None):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        try:
            node_type, pk = from_global_id(application_id)
            if node_type == 'OfferApplicationNode':
                application_id = int(pk)
            else:
                application_id = int(application_id)
        except Exception:
            try:
                application_id = int(application_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid application ID format.")

        try:
            application = OfferApplication.objects.select_related("offer").get(id=application_id)
        except OfferApplication.DoesNotExist:
            raise GraphQLError("Application not found.")

        if application.offer.created_by != user and not (user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("You are not allowed to mark escrow for this application.")

        if application.status != ApplicationStatus.APPROVED:
            raise GraphQLError("Only approved applications can be moved to escrow.")

        if application.payment_status in [PaymentStatus.IN_ESCROW, PaymentStatus.RELEASED]:
            raise GraphQLError("Payment is already in escrow or released.")

        application.payment_status = PaymentStatus.IN_ESCROW
        application.payment_reference = payment_reference or f"escrow-{application.id}-{int(timezone.now().timestamp())}"
        application.paid_at = timezone.now()
        application.save(update_fields=["payment_status", "payment_reference", "paid_at", "updated_at"])

        return MarkApplicationPaymentEscrow(ok=True, application=application)


class CreateApplicationCheckoutSession(graphene.Mutation):
    class Arguments:
        application_id = graphene.ID(required=True)

    ok = graphene.Boolean()
    checkout = graphene.Field(CheckoutSessionType)

    def mutate(self, info, application_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        try:
            node_type, pk = from_global_id(application_id)
            if node_type == 'OfferApplicationNode':
                application_id = int(pk)
            else:
                application_id = int(application_id)
        except Exception:
            try:
                application_id = int(application_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid application ID format.")

        try:
            application = OfferApplication.objects.select_related("offer", "user").get(id=application_id)
        except OfferApplication.DoesNotExist:
            raise GraphQLError("Application not found.")

        if application.offer.created_by != user and not (user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("You are not allowed to pay this application.")

        if application.status != ApplicationStatus.APPROVED:
            raise GraphQLError("Only approved applications can be paid.")

        if application.payment_status in [PaymentStatus.IN_ESCROW, PaymentStatus.RELEASED]:
            raise GraphQLError("This application is already paid.")

        amount_cents = int((application.asking_price * Decimal("100")).quantize(Decimal("1")))
        if amount_cents <= 0:
            raise GraphQLError("Invalid asking price for payment.")

        if settings.STRIPE_SIMULATION_MODE:
            # Local development shortcut: mark as paid in escrow without external Stripe dependency.
            application.payment_status = PaymentStatus.IN_ESCROW
            application.payment_reference = f"sim-escrow-{application.id}-{int(timezone.now().timestamp())}"
            application.paid_at = timezone.now()
            application.save(update_fields=["payment_status", "payment_reference", "paid_at", "updated_at"])

            simulated_session_id = f"sim_{application.id}_{int(timezone.now().timestamp())}"
            simulated_checkout_url = (
                f"{settings.FRONTEND_URL.rstrip('/')}"
                f"/company/dashboard?payment=success&session_id={simulated_session_id}"
            )

            return CreateApplicationCheckoutSession(
                ok=True,
                checkout=CheckoutSessionType(
                    session_id=simulated_session_id,
                    checkout_url=simulated_checkout_url,
                )
            )

        if not settings.STRIPE_SECRET_KEY:
            raise GraphQLError("Stripe is not configured on the server.")

        session_id, checkout_url = create_checkout_session(application, amount_cents)

        return CreateApplicationCheckoutSession(
            ok=True,
            checkout=CheckoutSessionType(
                session_id=session_id,
                checkout_url=checkout_url,
            )
        )


class ReleaseApplicationPayment(graphene.Mutation):
    class Arguments:
        application_id = graphene.ID(required=True)

    ok = graphene.Boolean()
    application = graphene.Field(OfferApplicationType)

    def mutate(self, info, application_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        try:
            node_type, pk = from_global_id(application_id)
            if node_type == 'OfferApplicationNode':
                application_id = int(pk)
            else:
                application_id = int(application_id)
        except Exception:
            try:
                application_id = int(application_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid application ID format.")

        try:
            application = OfferApplication.objects.select_related("offer").get(id=application_id)
        except OfferApplication.DoesNotExist:
            raise GraphQLError("Application not found.")

        if application.offer.created_by != user and not (user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("You are not allowed to release payment for this application.")

        if application.payment_status != PaymentStatus.IN_ESCROW:
            raise GraphQLError("Only escrowed payments can be released.")

        application.payment_status = PaymentStatus.RELEASED
        application.released_at = timezone.now()
        application.save(update_fields=["payment_status", "released_at", "updated_at"])

        return ReleaseApplicationPayment(ok=True, application=application)


class RefundApplicationPayment(graphene.Mutation):
    class Arguments:
        application_id = graphene.ID(required=True)

    ok = graphene.Boolean()
    application = graphene.Field(OfferApplicationType)

    def mutate(self, info, application_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        try:
            node_type, pk = from_global_id(application_id)
            if node_type == 'OfferApplicationNode':
                application_id = int(pk)
            else:
                application_id = int(application_id)
        except Exception:
            try:
                application_id = int(application_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid application ID format.")

        try:
            application = OfferApplication.objects.select_related("offer").get(id=application_id)
        except OfferApplication.DoesNotExist:
            raise GraphQLError("Application not found.")

        if application.offer.created_by != user and not (user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("You are not allowed to refund this application.")

        if application.payment_status != PaymentStatus.IN_ESCROW:
            raise GraphQLError("Only escrowed payments can be refunded.")

        application.payment_status = PaymentStatus.REFUNDED
        application.refunded_at = timezone.now()
        application.save(update_fields=["payment_status", "refunded_at", "updated_at"])

        return RefundApplicationPayment(ok=True, application=application)


class AddPaymentMethod(graphene.Mutation):
    class Arguments:
        method_type = graphene.String(required=True)
        label = graphene.String(required=True)
        details = graphene.String(required=True)
        is_primary = graphene.Boolean(required=False)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    errors = graphene.List(graphene.String)
    payment_method = graphene.Field(InfluencerPaymentMethodType)

    def mutate(self, info, method_type, label, details, is_primary=False):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        if not (check_user_role(user, "INFLUENCER") or user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("Only influencer accounts can add payment methods.")

        allowed_types = {choice[0] for choice in PaymentMethodType.choices}
        if method_type not in allowed_types:
            return AddPaymentMethod(
                success=False,
                message="Invalid payment method type.",
                errors=[f"Allowed types: {', '.join(sorted(allowed_types))}"],
                payment_method=None,
            )

        if is_primary:
            InfluencerPaymentMethod.objects.filter(user=user, is_primary=True).update(is_primary=False)

        payment_method = InfluencerPaymentMethod.objects.create(
            user=user,
            method_type=method_type,
            label=label,
            details=details,
            is_primary=is_primary or not InfluencerPaymentMethod.objects.filter(user=user).exists(),
        )

        return AddPaymentMethod(
            success=True,
            message="Payment method added successfully.",
            errors=[],
            payment_method=payment_method,
        )


class CreatePayoutRequest(graphene.Mutation):
    class Arguments:
        amount = graphene.Float(required=True)
        payment_method_id = graphene.ID(required=False)
        notes = graphene.String(required=False)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    errors = graphene.List(graphene.String)
    payout_request = graphene.Field(PayoutRequestType)
    available_balance = graphene.Float()

    def mutate(self, info, amount, payment_method_id=None, notes=None):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        if not (check_user_role(user, "INFLUENCER") or user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("Only influencer accounts can request payouts.")

        try:
            amount_decimal = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError):
            return CreatePayoutRequest(
                success=False,
                message="Invalid amount format.",
                errors=["Amount must be a valid number."],
                payout_request=None,
                available_balance=0,
            )

        if amount_decimal <= 0:
            return CreatePayoutRequest(
                success=False,
                message="Invalid payout amount.",
                errors=["Amount must be greater than zero."],
                payout_request=None,
                available_balance=0,
            )

        released_total = (
            OfferApplication.objects.filter(
                user=user,
            ).filter(
                Q(payment_status=PaymentStatus.RELEASED)
                | Q(payment_status__iexact="released")
                | Q(payment_status__icontains="released")
            )
            .aggregate(total=Sum("asking_price"))
            .get("total")
            or Decimal("0")
        )

        # Legacy fallback: if no payment has reached RELEASED yet,
        # allow payouts from approved applications to keep old flows functional.
        approved_total = (
            OfferApplication.objects.filter(
                user=user,
            ).filter(
                Q(status=ApplicationStatus.APPROVED)
                | Q(status__iexact="approved")
                | Q(status__icontains="approved")
            )
            .aggregate(total=Sum("asking_price"))
            .get("total")
            or Decimal("0")
        )

        eligible_total = released_total if released_total > 0 else approved_total

        reserved_total = (
            PayoutRequest.objects.filter(
                user=user,
                status__in=[
                    PayoutRequestStatus.PENDING,
                    PayoutRequestStatus.APPROVED,
                    PayoutRequestStatus.PAID,
                ],
            )
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0")
        )
        available_balance = eligible_total - reserved_total

        if amount_decimal > available_balance:
            return CreatePayoutRequest(
                success=False,
                message="Insufficient available balance.",
                errors=[
                    f"Available balance is ${available_balance}. You requested ${amount_decimal}."
                ],
                payout_request=None,
                available_balance=float(available_balance),
            )

        payment_method = None
        if payment_method_id:
            try:
                node_type, pk = from_global_id(payment_method_id)
                if node_type == 'InfluencerPaymentMethodType':
                    payment_method_id = int(pk)
                else:
                    payment_method_id = int(payment_method_id)
            except Exception:
                try:
                    payment_method_id = int(payment_method_id)
                except (ValueError, TypeError):
                    return CreatePayoutRequest(
                        success=False,
                        message="Invalid payment method ID format.",
                        errors=["Invalid payment method ID format."],
                        payout_request=None,
                        available_balance=float(available_balance),
                    )

            payment_method = InfluencerPaymentMethod.objects.filter(
                id=payment_method_id,
                user=user,
                is_active=True,
            ).first()
        else:
            payment_method = InfluencerPaymentMethod.objects.filter(
                user=user,
                is_active=True,
                is_primary=True,
            ).first() or InfluencerPaymentMethod.objects.filter(
                user=user,
                is_active=True,
            ).first()

        if payment_method is None:
            return CreatePayoutRequest(
                success=False,
                message="No active payment method found.",
                errors=["Please add a payment method before requesting payout."],
                payout_request=None,
                available_balance=float(available_balance),
            )

        payout_request = PayoutRequest.objects.create(
            user=user,
            amount=amount_decimal,
            payment_method=payment_method,
            notes=notes or "",
        )

        safe_create_notification(
            user=user,
            notification_type=NotificationType.PAYOUT,
            title="Payout request created",
            message=f"Your withdrawal request of ${amount_decimal} has been submitted.",
            link="/influencer/earnings",
            is_read=False,
        )

        admin_users = User.objects.filter(
            Q(is_staff=True)
            | Q(role='ADMIN')
            | Q(role__iexact='admin')
            | Q(role__icontains='ADMIN')
        ).exclude(id=user.id)

        for admin_user in admin_users:
            safe_create_notification(
                user=admin_user,
                notification_type=NotificationType.PAYOUT,
                title="New payout request",
                message=f"{user.name or user.email} requested ${amount_decimal} payout.",
                link="/admin",
                is_read=False,
            )

        return CreatePayoutRequest(
            success=True,
            message="Payout request created successfully.",
            errors=[],
            payout_request=payout_request,
            available_balance=float(available_balance - amount_decimal),
        )
