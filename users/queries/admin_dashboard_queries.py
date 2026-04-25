import graphene
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from users.models import User, UserRole
from offer.models import Offer, OfferApplication, ApplicationStatus, PaymentStatus

class ChartDataPointType(graphene.ObjectType):
    label = graphene.String()
    value = graphene.Float()

class AdminDashboardStatsType(graphene.ObjectType):
    total_revenue = graphene.Float()
    revenue_trend = graphene.List(ChartDataPointType)
    applications_status_dist = graphene.List(ChartDataPointType)
    users_role_dist = graphene.List(ChartDataPointType)
    offers_growth = graphene.List(ChartDataPointType)

class AdminDashboardQueries(graphene.ObjectType):
    admin_dashboard_stats = graphene.Field(AdminDashboardStatsType)

    def resolve_admin_dashboard_stats(self, info):
        now = timezone.now()
        six_months_ago = now - timedelta(days=180)

        # 1. Total Revenue (Released or In Escrow payments)
        total_revenue_query = OfferApplication.objects.filter(
            payment_status__in=[PaymentStatus.RELEASED, PaymentStatus.IN_ESCROW]
        ).aggregate(total=Sum('asking_price'))
        total_revenue = float(total_revenue_query['total'] or 0.0)

        # 2. Revenue Trend (Last 6 months)
        revenue_trend_raw = OfferApplication.objects.filter(
            payment_status__in=[PaymentStatus.RELEASED, PaymentStatus.IN_ESCROW],
            submitted_at__gte=six_months_ago
        ).annotate(month=TruncMonth('submitted_at')).values('month').annotate(total=Sum('asking_price')).order_by('month')

        revenue_trend = [
            ChartDataPointType(label=item['month'].strftime('%b %Y'), value=float(item['total'] or 0.0))
            for item in revenue_trend_raw
        ]

        # 3. Applications Status Distribution
        app_status_raw = OfferApplication.objects.values('status').annotate(count=Count('id'))
        applications_status_dist = [
            ChartDataPointType(label=item['status'], value=float(item['count']))
            for item in app_status_raw
        ]

        # 4. Users Role Distribution
        user_role_raw = User.objects.values('role').annotate(count=Count('id'))
        users_role_dist = [
            ChartDataPointType(label=item['role'], value=float(item['count']))
            for item in user_role_raw
        ]

        # 5. Offers Growth (New offers per month)
        offers_growth_raw = Offer.objects.filter(
            created_at__gte=six_months_ago
        ).annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')

        offers_growth = [
            ChartDataPointType(label=item['month'].strftime('%b %Y'), value=float(item['count']))
            for item in offers_growth_raw
        ]

        return AdminDashboardStatsType(
            total_revenue=total_revenue,
            revenue_trend=revenue_trend,
            applications_status_dist=applications_status_dist,
            users_role_dist=users_role_dist,
            offers_growth=offers_growth
        )
