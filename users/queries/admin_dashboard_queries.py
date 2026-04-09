import graphene
from datetime import timedelta
from django.utils import timezone
from users.models import User
from offer.models import Offer, OfferApplication

class SessionsTrendMediumType(graphene.ObjectType):
    label = graphene.String()
    data = graphene.List(graphene.Int)

class NewVsReturningType(graphene.ObjectType):
    new = graphene.Int()
    returning = graphene.Int()

class AdminDashboardStatsType(graphene.ObjectType):
    total_sessions = graphene.Int()
    sessions_trend_by_medium = graphene.List(SessionsTrendMediumType)
    pages_per_visit = graphene.Float()
    unique_visitors = graphene.Int()
    new_vs_returning = graphene.Field(NewVsReturningType)
    gender_breakdown = graphene.JSONString()

class AdminDashboardQueries(graphene.ObjectType):
    admin_dashboard_stats = graphene.Field(AdminDashboardStatsType)

    def resolve_admin_dashboard_stats(self, info):
        now = timezone.now()
        # Simule 12 mois
        months = [now - timedelta(days=30*i) for i in range(12)][::-1]
        # Sessions = users actifs (à adapter si tu as un modèle Session)
        total_sessions = User.objects.count()
        unique_visitors = User.objects.values('email').distinct().count()
        pages_per_visit = 1.76  # À calculer si tu as les logs
        sessions_trend_by_medium = [
            SessionsTrendMediumType(label="Direct", data=[100, 120, 90, 150, 200, 180, 160, 170, 140, 130, 120, 110]),
            SessionsTrendMediumType(label="Google", data=[80, 90, 70, 100, 120, 110, 100, 105, 95, 90, 85, 80]),
            SessionsTrendMediumType(label="Facebook", data=[60, 70, 50, 80, 100, 90, 80, 85, 75, 70, 65, 60]),
        ]
        new = User.objects.filter(created_at__gte=now - timedelta(days=30)).count()
        returning = unique_visitors - new
        gender_breakdown = {"Homme": 52.8, "Femme": 47.2}
        return AdminDashboardStatsType(
            total_sessions=total_sessions,
            sessions_trend_by_medium=sessions_trend_by_medium,
            pages_per_visit=pages_per_visit,
            unique_visitors=unique_visitors,
            new_vs_returning=NewVsReturningType(new=new, returning=returning),
            gender_breakdown=gender_breakdown,
        )
