import graphene
from .offer_single import OfferSingleQuery
from .offer_list import OfferListQuery
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Q

from offer.models import (
    Offer,
    OfferApplication,
    ApplicationStatus,
    PaymentStatus,
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
    created_by = graphene.Field(DashboardUserType)


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


class InfluencerDashboardStatsType(graphene.ObjectType):
    total_campaigns = graphene.Int()
    active_campaigns = graphene.Int()
    total_earnings = graphene.Float()
    pending_earnings = graphene.Float()
    available_balance = graphene.Float()
    total_reach = graphene.Int()
    avg_engagement = graphene.Float()
    recent_applications = graphene.List(DashboardApplicationType)
    monthly_earnings = graphene.JSONString()


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
    influencer_dashboard_stats = graphene.Field(
        InfluencerDashboardStatsType,
        description="Get dashboard statistics for the authenticated influencer"
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
                    created_by=DashboardUserType(
                        id=str(app.offer.created_by.id),
                        name=app.offer.created_by.name,
                        email=app.offer.created_by.email,
                    ),
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
            for app in applications_qs.select_related("offer", "user", "offer__created_by").order_by("-submitted_at")[:5]
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
    def resolve_influencer_dashboard_stats(self, info, **kwargs):
        user = info.context.user

        if not (check_user_role(user, "INFLUENCER") or user.is_staff or user.is_superuser):
            raise GraphQLError("This query is only available for influencer accounts")

        from users.influencer_models import Influencer
        try:
            influencer = Influencer.objects.prefetch_related(
                'reseaux_sociaux',
                'instagram_posts',
                'instagram_reels'
            ).get(user=user)
        except Influencer.DoesNotExist:
            return InfluencerDashboardStatsType(
                total_campaigns=0,
                active_campaigns=0,
                total_earnings=0.0,
                pending_earnings=0.0,
                available_balance=0.0,
                total_reach=0,
                avg_engagement=0.0,
                recent_applications=[],
                monthly_earnings='[]'
            )

        applications_qs = OfferApplication.objects.filter(user=user)
        
        # Earnings calculation
        released_total = float(
            applications_qs.filter(
                Q(payment_status=PaymentStatus.RELEASED)
                | Q(payment_status__iexact='released')
                | Q(payment_status__icontains='released')
            ).aggregate(total=Sum('asking_price'))['total']
            or 0
        )

        pending_total = float(
            applications_qs.filter(
                status=ApplicationStatus.APPROVED
            ).exclude(
                Q(payment_status=PaymentStatus.RELEASED)
                | Q(payment_status__iexact='released')
                | Q(payment_status__icontains='released')
            ).aggregate(total=Sum('asking_price'))['total']
            or 0
        )

        # Reserved (already requested or paid out)
        from offer.models import PayoutRequestStatus
        reserved_total = float(
            PayoutRequest.objects.filter(
                user=user,
                status__in=[
                    PayoutRequestStatus.PENDING,
                    PayoutRequestStatus.APPROVED,
                    PayoutRequestStatus.PAID,
                ],
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        available_balance = max(0.0, released_total - reserved_total)
        total_earnings = released_total + pending_total

        # Monthly earnings (for the chart)
        import datetime
        from django.db.models.functions import TruncMonth
        import json
        
        monthly_data = (
            applications_qs.filter(
                Q(payment_status=PaymentStatus.RELEASED)
                | Q(payment_status=PaymentStatus.IN_ESCROW)
                | Q(status=ApplicationStatus.APPROVED)
            )
            .annotate(month=TruncMonth('submitted_at'))
            .values('month')
            .annotate(total=Sum('asking_price'))
            .order_by('month')
        )
        
        monthly_earnings_list = []
        for entry in monthly_data:
            if entry['month']:
                monthly_earnings_list.append({
                    "month": entry['month'].strftime('%B'),
                    "amount": float(entry['total'])
                })
        
        # Reach and Engagement
        social_networks = list(influencer.reseaux_sociaux.all())
        total_reach = int(sum((rs.nombre_abonnes or 0) for rs in social_networks))
        
        avg_engagement = 0.0
        if social_networks:
            avg_engagement = float(sum((rs.taux_engagement or 0.0) for rs in social_networks) / len(social_networks))

        # Recent Applications
        recent_applications = [
            DashboardApplicationType(
                id=str(app.id),
                offer=DashboardApplicationOfferType(
                    id=str(app.offer.id),
                    title=app.offer.title,
                    created_by=DashboardUserType(
                        id=str(app.offer.created_by.id),
                        name=app.offer.created_by.name,
                        email=app.offer.created_by.email,
                    ),
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
            for app in applications_qs.select_related("offer", "user", "offer__created_by").order_by("-submitted_at")[:10]
        ]

        return InfluencerDashboardStatsType(
            total_campaigns=applications_qs.count(),
            active_campaigns=applications_qs.filter(status=ApplicationStatus.APPROVED).count(),
            total_earnings=total_earnings,
            pending_earnings=pending_total,
            available_balance=available_balance,
            total_reach=total_reach,
            avg_engagement=avg_engagement,
            recent_applications=recent_applications,
            monthly_earnings=monthly_earnings_list
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
