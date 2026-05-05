import graphene
from graphql import GraphQLError
from graphql_relay import from_global_id
from django.contrib.auth import get_user_model
from graphene_django.filter import DjangoFilterConnectionField
from django.db.models import Sum, Q

from ..influencer_models import Influencer
from ..influencer_node import InfluencerNode
from ..filters import InfluencerFilter
from ..utils import check_user_role, normalize_role
from offer.models import OfferApplication, ApplicationStatus, PaymentStatus

User = get_user_model()


class InfluencerKpiDebugType(graphene.ObjectType):
    earnings_source = graphene.String()
    earnings_released_total = graphene.Float()
    earnings_approved_total = graphene.Float()
    earnings_final_total = graphene.Float()

    reach_source = graphene.String()
    reach_social_total = graphene.Int()
    reach_instagram_total = graphene.Int()
    reach_final_total = graphene.Int()

    engagement_source = graphene.String()
    engagement_social_avg = graphene.Float()
    engagement_instagram_value = graphene.Float()
    engagement_content_value = graphene.Float()
    engagement_final_value = graphene.Float()

    social_networks_count = graphene.Int()
    instagram_posts_count = graphene.Int()
    instagram_reels_count = graphene.Int()


class InfluencerQueries(graphene.ObjectType):
    """Queries for influencer profiles"""
    
    # Get current user's influencer profile
    my_influencer_profile = graphene.Field(InfluencerNode)
    my_influencer_kpi_debug = graphene.Field(InfluencerKpiDebugType)
    
    # Get influencer by user ID
    influencer_by_user = graphene.Field(
        InfluencerNode,
        user_id=graphene.ID(required=True)
    )
    
    # Get influencer by ID (relay Node field)
    influencer = graphene.relay.Node.Field(InfluencerNode)
    
    # List all influencers with filtering, pagination, and totalCount
    all_influencers = DjangoFilterConnectionField(
        InfluencerNode,
        filterset_class=InfluencerFilter,
        description="Get all influencers with pagination, filtering, and totalCount in edges"
    )
    
    # Search influencers
    search_influencers = graphene.List(
        InfluencerNode,
        query=graphene.String(required=True),
        localisation=graphene.String(),
        min_followers=graphene.Int(),
        max_followers=graphene.Int(),
        min_engagement=graphene.Float(),
        category_ids=graphene.List(graphene.ID)
    )
    
    def resolve_my_influencer_profile(self, info):
        """Get current authenticated user's influencer profile"""
        user = info.context.user
        
        if not user.is_authenticated:
            raise GraphQLError('Authentication required')
        
        # Get user from database to ensure we have the latest role
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            # Refresh user from database
            user = User.objects.get(pk=user.pk)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        print(f'User role: {user.role} (type: {type(user.role)})')
        
        
        if not check_user_role(user, 'INFLUENCER'):
            return None
        
        try:
            return Influencer.objects.get(user=user)
        except Influencer.DoesNotExist:
            return None

    def resolve_my_influencer_kpi_debug(self, info):
        """Return KPI values and their data sources for fast troubleshooting."""
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError('Authentication required')

        if not check_user_role(user, 'INFLUENCER'):
            raise GraphQLError('This query is only available for influencer accounts')

        try:
            influencer = Influencer.objects.prefetch_related(
                'reseaux_sociaux',
                'instagram_posts',
                'instagram_reels',
                'statistiques_historique',
            ).get(user=user)
        except Influencer.DoesNotExist:
            return InfluencerKpiDebugType(
                earnings_source='no_profile',
                earnings_released_total=0.0,
                earnings_approved_total=0.0,
                earnings_final_total=0.0,
                reach_source='no_profile',
                reach_social_total=0,
                reach_instagram_total=0,
                reach_final_total=0,
                engagement_source='no_profile',
                engagement_social_avg=0.0,
                engagement_instagram_value=0.0,
                engagement_content_value=0.0,
                engagement_final_value=0.0,
                social_networks_count=0,
                instagram_posts_count=0,
                instagram_reels_count=0,
            )

        applications = OfferApplication.objects.filter(user=user)

        released_total = float(
            applications.filter(
                Q(payment_status=PaymentStatus.RELEASED)
                | Q(payment_status__iexact='released')
                | Q(payment_status__icontains='released')
            ).aggregate(total=Sum('asking_price'))['total']
            or 0
        )

        approved_total = float(
            applications.filter(
                Q(status=ApplicationStatus.APPROVED)
                | Q(status__iexact='approved')
                | Q(status__icontains='approved')
            ).aggregate(total=Sum('asking_price'))['total']
            or 0
        )

        if released_total > 0:
            earnings_source = 'released'
            earnings_final_total = released_total
        elif approved_total > 0:
            earnings_source = 'approved_fallback'
            earnings_final_total = approved_total
        else:
            earnings_source = 'none'
            earnings_final_total = 0.0

        social_networks = list(influencer.reseaux_sociaux.all())
        social_networks_count = len(social_networks)
        social_total = int(sum((rs.nombre_abonnes or 0) for rs in social_networks))
        instagram_total = int(
            influencer._extract_instagram_numeric(
                ['followers', 'follower_count', 'followers_count', 'edge_followed_by', 'nombre_abonnes'],
                default=0.0,
            )
        )

        if social_total > 0:
            reach_source = 'reseaux_sociaux'
            reach_final_total = social_total
        elif instagram_total > 0:
            reach_source = 'instagram_data'
            reach_final_total = instagram_total
        else:
            reels = list(influencer.instagram_reels.all())
            views_total = sum((reel.views or 0) for reel in reels)
            if views_total > 0 and len(reels) > 0:
                reach_source = 'reels_views_estimate'
                reach_final_total = int(views_total / len(reels))
            else:
                reach_source = 'none'
                reach_final_total = 0

        social_avg = 0.0
        if social_networks_count > 0:
            social_avg = float(sum((rs.taux_engagement or 0.0) for rs in social_networks) / social_networks_count)

        instagram_engagement = float(
            influencer._extract_instagram_numeric(
                ['engagement_rate', 'taux_engagement', 'engagement'],
                default=0.0,
            )
        )

        posts = list(influencer.instagram_posts.all())
        reels = list(influencer.instagram_reels.all())
        instagram_posts_count = len(posts)
        instagram_reels_count = len(reels)
        total_content = instagram_posts_count + instagram_reels_count
        total_interactions = 0
        for post in posts:
            total_interactions += (post.likes or 0) + (post.comments or 0)
        for reel in reels:
            total_interactions += (reel.likes or 0) + (reel.comments or 0)

        engagement_content_value = 0.0
        if total_content > 0 and reach_final_total > 0:
            engagement_content_value = float((total_interactions / total_content) / reach_final_total * 100)

        if social_avg > 0:
            engagement_source = 'reseaux_sociaux'
            engagement_final_value = social_avg
        elif instagram_engagement > 0:
            engagement_source = 'instagram_data'
            engagement_final_value = instagram_engagement
        elif engagement_content_value > 0:
            engagement_source = 'posts_reels_computed'
            engagement_final_value = engagement_content_value
        else:
            engagement_source = 'none'
            engagement_final_value = 0.0

        return InfluencerKpiDebugType(
            earnings_source=earnings_source,
            earnings_released_total=released_total,
            earnings_approved_total=approved_total,
            earnings_final_total=earnings_final_total,
            reach_source=reach_source,
            reach_social_total=social_total,
            reach_instagram_total=instagram_total,
            reach_final_total=reach_final_total,
            engagement_source=engagement_source,
            engagement_social_avg=social_avg,
            engagement_instagram_value=instagram_engagement,
            engagement_content_value=engagement_content_value,
            engagement_final_value=engagement_final_value,
            social_networks_count=social_networks_count,
            instagram_posts_count=instagram_posts_count,
            instagram_reels_count=instagram_reels_count,
        )
    
    def resolve_influencer_by_user(self, info, user_id):
        """Get influencer profile by user ID (accepts both integer and global ID)"""
        try:
            # Try to decode global ID if it's in relay format
            try:
                node_type, pk = from_global_id(user_id)
                # Accept both UserNode and InfluencerNode IDs
                if node_type not in ['UserNode', 'InfluencerNode']:
                    raise ValueError('Invalid node type')
                user_id = pk
            except Exception:
                # If it's not a valid global ID, assume it's a regular integer ID
                pass
            
            user = User.objects.get(pk=user_id)
            if not check_user_role(user, 'INFLUENCER'):
                raise GraphQLError('User is not an influencer')
            
            # Fetch influencer with all related data prefetched
            return Influencer.objects.prefetch_related(
                'images',
                'instagram_posts',
                'instagram_reels',
                'reseaux_sociaux',
                'offres_collaboration',
                'previous_works',
                'portfolio_media',
                'selected_categories'
            ).select_related('user').get(user=user)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        except Influencer.DoesNotExist:
            raise GraphQLError('Influencer profile not found')
    
    def resolve_search_influencers(self, info, query, localisation=None, 
                                  min_followers=None, max_followers=None,
                                  min_engagement=None, category_ids=None):
        """Search influencers with advanced filters"""
        from django.db.models import Q
        
        # Search in multiple fields
        queryset = Influencer.objects.filter(
            Q(pseudo__icontains=query) |
            Q(biography__icontains=query) |
            Q(user__name__icontains=query) |
            Q(centres_interet__icontains=query)
        )
        
        # Apply additional filters
        if localisation:
            queryset = queryset.filter(localisation__icontains=localisation)
        
        if category_ids:
            queryset = queryset.filter(selected_categories__id__in=category_ids).distinct()
        
        # Filter by followers and engagement (requires calculation)
        results = []
        for influencer in queryset:
            followers = influencer.followers_totaux
            engagement = influencer.engagement_moyen_global
            
            if min_followers and followers < min_followers:
                continue
            if max_followers and followers > max_followers:
                continue
            if min_engagement and engagement < min_engagement:
                continue
            
            results.append(influencer)
        
        return results
