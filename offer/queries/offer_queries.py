import graphene
from .offer_single import OfferSingleQuery
from .offer_list import OfferListQuery
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from django.utils import timezone

from offer.models import (
    Offer,
    OfferApplication,
    ApplicationStatus,
    InfluencerPaymentMethod,
    PayoutRequest,
)
from users.utils import check_user_role


class DashboardOfferType(graphene.ObjectType):
    id = graphene.ID()
    title = graphene.String()
    min_budget = graphene.Float()
    max_budget = graphene.Float()
    start_date = graphene.Date()
    end_date = graphene.Date()
    influencer_number = graphene.Int()
    created_at = graphene.DateTime()


class DashboardUserType(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    email = graphene.String()


class DashboardApplicationOfferType(graphene.ObjectType):
    id = graphene.ID()
    title = graphene.String()


class DashboardApplicationType(graphene.ObjectType):
    id = graphene.ID()
    offer = graphene.Field(DashboardApplicationOfferType)
    user = graphene.Field(DashboardUserType)
    status = graphene.String()
    payment_status = graphene.String()
    asking_price = graphene.Float()
    submitted_at = graphene.DateTime()


class CompanyDashboardStatsType(graphene.ObjectType):
    total_offers = graphene.Int()
    active_offers = graphene.Int()
    total_applications = graphene.Int()
    pending_applications = graphene.Int()
    approved_applications = graphene.Int()
    rejected_applications = graphene.Int()
    recent_offers = graphene.List(DashboardOfferType)
    recent_applications = graphene.List(DashboardApplicationType)


class InfluencerPaymentMethodType(graphene.ObjectType):
    id = graphene.ID()
    method_type = graphene.String()
    label = graphene.String()
    details = graphene.String()
    is_primary = graphene.Boolean()
    is_active = graphene.Boolean()
    created_at = graphene.DateTime()


class PayoutRequestType(graphene.ObjectType):
    id = graphene.ID()
    amount = graphene.Float()
    status = graphene.String()
    requested_at = graphene.DateTime()
    processed_at = graphene.DateTime()
    notes = graphene.String()
    payment_method = graphene.Field(InfluencerPaymentMethodType)

class OfferQueries(OfferSingleQuery, OfferListQuery):
    """All offer queries in one place"""

    company_dashboard_stats = graphene.Field(
        CompanyDashboardStatsType,
        description="Get dashboard statistics for the authenticated company"
    )
    my_payment_methods = graphene.List(
        InfluencerPaymentMethodType,
        description="Get current influencer payment methods"
    )
    my_payout_requests = graphene.List(
        PayoutRequestType,
        description="Get current influencer payout requests"
    )

    @login_required
    def resolve_company_dashboard_stats(self, info, **kwargs):
        user = info.context.user

        if not check_user_role(user, "COMPANY") and not user.is_staff and not user.is_superuser:
            raise GraphQLError("This query is only available for company accounts")

        offers_qs = Offer.objects.filter(created_by=user)
        today = timezone.localdate()

        active_offers_count = offers_qs.filter(end_date__gte=today).count()
        applications_qs = OfferApplication.objects.filter(offer__created_by=user)

        recent_offers = [
            DashboardOfferType(
                id=str(offer.id),
                title=offer.title,
                min_budget=float(offer.min_budget),
                max_budget=float(offer.max_budget),
                start_date=offer.start_date,
                end_date=offer.end_date,
                influencer_number=offer.influencer_number,
                created_at=offer.created_at,
            )
            for offer in offers_qs.order_by("-created_at")[:5]
        ]

        recent_applications = [
            DashboardApplicationType(
                id=str(app.id),
                offer=DashboardApplicationOfferType(
                    id=str(app.offer.id),
                    title=app.offer.title,
                ),
                user=DashboardUserType(
                    id=str(app.user.id),
                    name=app.user.name,
                    email=app.user.email,
                ),
                status=app.status,
                payment_status=app.payment_status,
                asking_price=float(app.asking_price),
                submitted_at=app.submitted_at,
            )
            for app in applications_qs.select_related("offer", "user").order_by("-submitted_at")[:5]
        ]

        return CompanyDashboardStatsType(
            total_offers=offers_qs.count(),
            active_offers=active_offers_count,
            total_applications=applications_qs.count(),
            pending_applications=applications_qs.filter(status=ApplicationStatus.PENDING).count(),
            approved_applications=applications_qs.filter(status=ApplicationStatus.APPROVED).count(),
            rejected_applications=applications_qs.filter(status=ApplicationStatus.REJECTED).count(),
            recent_offers=recent_offers,
            recent_applications=recent_applications,
        )

    @login_required
    def resolve_my_payment_methods(self, info, **kwargs):
        user = info.context.user

        if not (check_user_role(user, "INFLUENCER") or user.is_staff or user.is_superuser):
            raise GraphQLError("This query is only available for influencer accounts")

        methods = InfluencerPaymentMethod.objects.filter(user=user, is_active=True).order_by("-is_primary", "-created_at")

        return [
            InfluencerPaymentMethodType(
                id=str(method.id),
                method_type=method.method_type,
                label=method.label,
                details=method.details,
                is_primary=method.is_primary,
                is_active=method.is_active,
                created_at=method.created_at,
            )
            for method in methods
        ]

    @login_required
    def resolve_my_payout_requests(self, info, **kwargs):
        user = info.context.user

        if not (check_user_role(user, "INFLUENCER") or user.is_staff or user.is_superuser):
            raise GraphQLError("This query is only available for influencer accounts")

        payout_requests = PayoutRequest.objects.select_related("payment_method").filter(user=user).order_by("-requested_at")

        return [
            PayoutRequestType(
                id=str(request.id),
                amount=float(request.amount),
                status=request.status,
                requested_at=request.requested_at,
                processed_at=request.processed_at,
                notes=request.notes,
                payment_method=InfluencerPaymentMethodType(
                    id=str(request.payment_method.id),
                    method_type=request.payment_method.method_type,
                    label=request.payment_method.label,
                    details=request.payment_method.details,
                    is_primary=request.payment_method.is_primary,
                    is_active=request.payment_method.is_active,
                    created_at=request.payment_method.created_at,
                ) if request.payment_method else None,
            )
            for request in payout_requests
        ]
