import graphene
from graphene_django import DjangoObjectType
from graphene import relay
from .influencer_models import (
    Influencer, ReseauSocial, InfluencerWork, Image,
    InstagramReel, InstagramPost,
    PortfolioMedia, OffreCollaboration, StatistiquesGlobales
)
from .utils import normalize_role
from category.types import CategoryNode


def normalize_enum_value(value):
    """Extract clean enum value from corrupted string like 'EnumMeta.DISPONIBLE'"""
    if not value:
        return value
    if isinstance(value, str) and '.' in value:
        return value.split('.')[-1]
    return value


class DisponibiliteEnum(graphene.Enum):
    """Enum for collaboration availability"""
    DISPONIBLE = 'disponible'
    OCCUPE = 'occupe'
    PARTIELLEMENT_DISPONIBLE = 'partiellement_disponible'


class PlateformeEnum(graphene.Enum):
    """Enum for social media platforms"""
    INSTAGRAM = 'Instagram'
    TIKTOK = 'TikTok'
    YOUTUBE = 'YouTube'
    FACEBOOK = 'Facebook'
    TWITTER = 'Twitter'
    LINKEDIN = 'LinkedIn'
    SNAPCHAT = 'Snapchat'


class FrequencePublicationEnum(graphene.Enum):
    """Enum for publication frequency"""
    QUOTIDIENNE = 'quotidienne'
    HEBDOMADAIRE = 'hebdomadaire'
    BI_HEBDOMADAIRE = 'bi_hebdomadaire'
    MENSUELLE = 'mensuelle'


class TypeCollaborationEnum(graphene.Enum):
    """Enum for collaboration type"""
    PLACEMENT_PRODUIT = 'placement_produit'
    STORY = 'story'
    POST = 'post'
    VIDEO = 'video'
    REEL = 'reel'
    LIVE = 'live'
    AMBASSADEUR = 'ambassadeur'


class ReseauSocialNode(DjangoObjectType):
    """GraphQL Node for ReseauSocial model"""
    plateforme = graphene.Field(PlateformeEnum)
    frequence_publication = graphene.Field(FrequencePublicationEnum)
    
    class Meta:
        model = ReseauSocial
        fields = (
            'id', 'plateforme', 'url_profil', 'nombre_abonnes', 
            'taux_engagement', 'moyenne_vues', 'moyenne_likes',
            'moyenne_commentaires', 'frequence_publication',
            'created_at', 'updated_at'
        )
        interfaces = (graphene.relay.Node,)
    
    def resolve_plateforme(self, info):
        """Normalize plateforme value to handle corrupted data"""
        clean_value = normalize_enum_value(self.plateforme)
        # Return the clean value which will be matched against the enum
        return clean_value
    
    def resolve_frequence_publication(self, info):
        """Normalize frequence_publication value to handle corrupted data"""
        clean_value = normalize_enum_value(self.frequence_publication)
        # Return the clean value which will be matched against the enum
        return clean_value


class InfluencerWorkNode(DjangoObjectType):
    """GraphQL Node for InfluencerWork model"""
    
    class Meta:
        model = InfluencerWork
        fields = (
            'id', 'brand_name', 'campaign', 'period', 
            'results', 'publication_link',
            'created_at', 'updated_at'
        )
        interfaces = (graphene.relay.Node,)


class ImageNode(DjangoObjectType):
    """GraphQL Node for generic Image model"""
    
    class Meta:
        model = Image
        fields = (
            'id', 'url', 'is_default', 'is_public', 'created_at'
        )
        interfaces = (graphene.relay.Node,)


class InstagramReelNode(DjangoObjectType):
    """GraphQL Node for Instagram Reel"""
    
    class Meta:
        model = InstagramReel
        fields = (
            'id', 'instagram_id', 'code', 'video_url', 'thumbnail_url',
            'post_name', 'duration', 'taken_at', 'likes', 'comments',
            'views', 'username', 'hashtags', 'created_at', 'updated_at'
        )
        interfaces = (graphene.relay.Node,)


class InstagramPostNode(DjangoObjectType):
    """GraphQL Node for Instagram Post"""
    
    class Meta:
        model = InstagramPost
        fields = (
            'id', 'instagram_id', 'code', 'media_type', 'image_url',
            'thumbnail_url', 'post_name', 'taken_at', 'likes', 'comments',
            'username', 'carousel_media', 'hashtags', 'created_at', 'updated_at'
        )
        interfaces = (graphene.relay.Node,)


class PortfolioMediaNode(DjangoObjectType):
    """GraphQL Node for PortfolioMedia model"""
    
    class Meta:
        model = PortfolioMedia
        fields = (
            'id', 'image_url', 'titre', 'description', 
            'date_creation', 'created_at', 'updated_at'
        )
        interfaces = (graphene.relay.Node,)


class OffreCollaborationNode(DjangoObjectType):
    """GraphQL Node for OffreCollaboration model"""
    type_collaboration = graphene.Field(TypeCollaborationEnum)
    
    class Meta:
        model = OffreCollaboration
        fields = (
            'id', 'type_collaboration', 'tarif_minimum', 
            'tarif_maximum', 'conditions',
            'created_at', 'updated_at'
        )
        interfaces = (graphene.relay.Node,)
    
    def resolve_type_collaboration(self, info):
        """Normalize type_collaboration value to handle corrupted data"""
        clean_value = normalize_enum_value(self.type_collaboration)
        return clean_value


class StatistiquesGlobalesNode(DjangoObjectType):
    """GraphQL Node for StatistiquesGlobales model"""
    
    class Meta:
        model = StatistiquesGlobales
        fields = (
            'id', 'followers_totaux', 'engagement_moyen_global',
            'croissance_mensuelle', 'mois', 'created_at'
        )
        interfaces = (graphene.relay.Node,)


class StatistiquesGlobalesType(graphene.ObjectType):
    """Type for current global statistics"""
    followers_totaux = graphene.Int()
    engagement_moyen_global = graphene.Float()
    croissance_mensuelle = graphene.Float()


class InfluencerConnection(relay.Connection):
    """Connection for Influencer with totalCount and offset pagination support"""
    
    total_count = graphene.Int()
    
    class Meta:
        abstract = True
    
    def resolve_total_count(root, info, **kwargs):
        """Resolve total count from stored length or iterable"""
        return root.length if hasattr(root, 'length') else (
            root.iterable.count() if hasattr(root, 'iterable') and hasattr(root.iterable, 'count') else len(root.edges)
        )


class InfluencerNode(DjangoObjectType):
    """GraphQL Node for Influencer model"""
    disponibilite_collaboration = graphene.Field(DisponibiliteEnum)
    selected_categories = graphene.List(CategoryNode)
    langues = graphene.List(graphene.String)
    centres_interet = graphene.List(graphene.String)
    type_contenu = graphene.List(graphene.String)
    instagram_data = graphene.JSONString()
    reseaux_sociaux = graphene.List(ReseauSocialNode)
    previous_works = graphene.List(InfluencerWorkNode)
    images = graphene.List(ImageNode)
    instagram_reels = graphene.List(InstagramReelNode)
    instagram_posts = graphene.List(InstagramPostNode)
    portfolio_media = graphene.List(PortfolioMediaNode)
    offres_collaboration = graphene.List(OffreCollaborationNode)
    statistiques_globales = graphene.Field(StatistiquesGlobalesType)
    profile_picture = graphene.String()
    
    class Meta:
        model = Influencer
        fields = (
            'id', 'user', 'instagram_username', 'pseudo', 'biography',
            'site_web', 'localisation', 'instagram_data', 'selected_categories',
            'langues', 'centres_interet', 'type_contenu',
            'disponibilite_collaboration', 'created_at', 'updated_at', 'profile_picture'
        )
        interfaces = (graphene.relay.Node,)
        connection_class = InfluencerConnection
    
    def resolve_disponibilite_collaboration(self, info):
        """Normalize disponibilite_collaboration value to handle corrupted data"""
        clean_value = normalize_enum_value(self.disponibilite_collaboration)
        return clean_value
    
    def resolve_selected_categories(self, info):
        return self.selected_categories.all()
    
    def resolve_reseaux_sociaux(self, info):
        return self.reseaux_sociaux.all()
    
    def resolve_previous_works(self, info):
        return self.previous_works.all()
    
    def resolve_images(self, info):
        return self.images.all()
    
    def resolve_instagram_reels(self, info):
        return self.instagram_reels.all()
    
    def resolve_instagram_posts(self, info):
        return self.instagram_posts.all()
    
    def resolve_portfolio_media(self, info):
        return self.portfolio_media.all()
    
    def resolve_offres_collaboration(self, info):
        return self.offres_collaboration.all()
    
    def resolve_statistiques_globales(self, info):
        """Return current global statistics"""
        return {
            'followers_totaux': self.followers_totaux,
            'engagement_moyen_global': self.engagement_moyen_global,
            'croissance_mensuelle': self.calculate_croissance_mensuelle()
        }

    def resolve_profile_picture(self, info):
        """Resolve profile picture from images relation"""
        try:
            profile_pic = self.images.filter(is_default=True).first()
            if not profile_pic:
                profile_pic = self.images.first()
            if profile_pic:
                return profile_pic.url
        except Exception:
            pass
        return None
