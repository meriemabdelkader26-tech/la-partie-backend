"""
Consolidated Influencer Mutations
All influencer-related operations including profile completion and updates
"""
import graphene
from graphql import GraphQLError
from graphql_relay import from_global_id
from django.contrib.auth import get_user_model
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from datetime import datetime

from ..influencer_models import (
    Influencer, ReseauSocial, InfluencerWork, Image,
    InstagramReel, InstagramPost,
    PortfolioMedia, OffreCollaboration
)
from ..influencer_node import (
    InfluencerNode, InfluencerWorkNode, ImageNode,
    InstagramReelNode, InstagramPostNode,
    DisponibiliteEnum, PlateformeEnum,
    FrequencePublicationEnum, TypeCollaborationEnum
)
from ..utils import normalize_role, check_user_role
from ..user_node import UserNode
from category.models import Category

User = get_user_model()


# Input types for nested objects
class ReseauSocialInput(graphene.InputObjectType):
    plateforme = graphene.Argument(PlateformeEnum, required=True)
    url_profil = graphene.String(required=True)
    nombre_abonnes = graphene.String(required=True)
    taux_engagement = graphene.String(required=True)
    moyenne_vues = graphene.String()
    moyenne_likes = graphene.String()
    moyenne_commentaires = graphene.String()
    frequence_publication = graphene.Argument(FrequencePublicationEnum)


class InfluencerWorkInput(graphene.InputObjectType):
    nom_marque = graphene.String(required=True)
    campagne = graphene.String(required=True)
    periode = graphene.String(required=True)
    resultats = graphene.String()
    lien_publication = graphene.String()


class ImageInput(graphene.InputObjectType):
    url = graphene.String(required=True)
    is_default = graphene.Boolean()
    is_public = graphene.Boolean()


class InstagramReelInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    code = graphene.String(required=True)
    video_url = graphene.String(required=True)
    thumbnail_url = graphene.String(required=True)
    post_name = graphene.String(required=True)
    duration = graphene.Int(required=True)
    taken_at = graphene.String(required=True)
    likes = graphene.Int(required=True)
    comments = graphene.Int(required=True)
    views = graphene.Int(required=True)
    username = graphene.String(required=True)
    hashtags = graphene.List(graphene.String)


class CarouselMediaInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    image_url = graphene.String(required=True)
    thumbnail_url = graphene.String(required=True)
    is_video = graphene.Boolean(required=True)


class InstagramPostInput(graphene.InputObjectType):
    id = graphene.String(required=True)
    code = graphene.String(required=True)
    media_type = graphene.String(required=True)
    image_url = graphene.String(required=True)
    thumbnail_url = graphene.String(required=True)
    post_name = graphene.String(required=True)
    taken_at = graphene.String(required=True)
    likes = graphene.Int(required=True)
    comments = graphene.Int(required=True)
    username = graphene.String(required=True)
    carousel_media = graphene.List(CarouselMediaInput)
    hashtags = graphene.List(graphene.String)


class PortfolioMediaInput(graphene.InputObjectType):
    image_url = graphene.String(required=True)
    title = graphene.String(required=True)
    description = graphene.String()
    date_creation = graphene.String()


class OffreCollaborationInput(graphene.InputObjectType):
    type_collaboration = graphene.Argument(TypeCollaborationEnum, required=True)
    tarif_minimum = graphene.String(required=True)
    tarif_maximum = graphene.String(required=True)
    conditions = graphene.String()


class InstagramDataInput(graphene.InputObjectType):
    """Instagram API data from Step 1"""
    username = graphene.String(required=True)
    full_name = graphene.String()
    biography = graphene.String()
    follower_count = graphene.Int()
    following_count = graphene.Int()
    media_count = graphene.Int()
    public_email = graphene.String()
    biography_email = graphene.String()
    contact_phone_number = graphene.String()
    external_url = graphene.String()
    profile_pic_url = graphene.String()
    is_verified = graphene.Boolean()
    is_private = graphene.Boolean()


class CompleteInfluencerProfile(graphene.Mutation):
    """Complete influencer profile with all information"""
    
    influencer = graphene.Field(InfluencerNode)
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        # Basic Information
        instagram_username = graphene.String(required=True)
        pseudo = graphene.String()
        instagram_data = graphene.Argument(InstagramDataInput)
        biography = graphene.String(required=True)
        site_web = graphene.String()
        localisation = graphene.String(required=True)
        
        # Categories and Interests
        selected_categories = graphene.List(graphene.ID, required=True)
        langues = graphene.List(graphene.String, required=True)
        centres_interet = graphene.List(graphene.String)
        type_contenu = graphene.List(graphene.String, required=True)
        
        # Collaboration
        disponibilite_collaboration = graphene.Argument(DisponibiliteEnum)
        
        # Related objects
        reseaux_sociaux = graphene.List(ReseauSocialInput, required=True)
        offres_collaboration = graphene.List(OffreCollaborationInput)
        
        # Portfolio & Past Work
        portfolio_media = graphene.List(PortfolioMediaInput)
        selected_reels = graphene.List(InstagramReelInput)
        selected_posts = graphene.List(InstagramPostInput)
        collaborations = graphene.List(InfluencerWorkInput)
        
        # Images
        images = graphene.List(ImageInput)
    
    @transaction.atomic
    def mutate(self, info, **kwargs):
        user = info.context.user
        
        if not user.is_authenticated:
            raise GraphQLError('Authentication required')
        
        # Debug: Check what's in the request context
        print(f"\n{'='*80}")
        print(f"🔍 DEBUG: CompleteInfluencerProfile mutation called")
        print(f"{'='*80}")
        print(f"📋 User from context: {user.name} ({user.email})")
        print(f"🆔 User ID: {user.id}")
        print(f"👤 Role: '{user.role}' (type: {type(user.role)})")
        
        # Check if there's token info in the request
        request = info.context
        if hasattr(request, 'META'):
            auth_header = request.META.get('HTTP_AUTHORIZATION', 'No auth header')
            print(f"🔑 Auth Header: {auth_header[:50]}..." if len(auth_header) > 50 else f"🔑 Auth Header: {auth_header}")
        print(f"{'='*80}\n")
        
        if not check_user_role(user, 'INFLUENCER'):
            raise GraphQLError(f'This action is only available for influencer accounts. Current role: {user.role}')
        
        influencer, created = Influencer.objects.get_or_create(user=user)
        
        # Update basic information
        influencer.instagram_username = kwargs.get('instagram_username')
        influencer.pseudo = kwargs.get('pseudo', '')
        influencer.biography = kwargs.get('biography')
        influencer.site_web = kwargs.get('site_web', '')
        influencer.localisation = kwargs.get('localisation')
        
        # Store Instagram API data
        if 'instagram_data' in kwargs and kwargs['instagram_data']:
            instagram_data = kwargs['instagram_data']
            influencer.instagram_data = {
                'username': instagram_data.get('username'),
                'full_name': instagram_data.get('full_name'),
                'biography': instagram_data.get('biography'),
                'follower_count': instagram_data.get('follower_count'),
                'following_count': instagram_data.get('following_count'),
                'media_count': instagram_data.get('media_count'),
                'public_email': instagram_data.get('public_email'),
                'biography_email': instagram_data.get('biography_email'),
                'contact_phone_number': instagram_data.get('contact_phone_number'),
                'external_url': instagram_data.get('external_url'),
                'profile_pic_url': instagram_data.get('profile_pic_url'),
                'is_verified': instagram_data.get('is_verified'),
                'is_private': instagram_data.get('is_private'),
            }
        
        influencer.langues = kwargs.get('langues', [])
        influencer.centres_interet = kwargs.get('centres_interet', [])
        influencer.type_contenu = kwargs.get('type_contenu', [])
        
        if 'disponibilite_collaboration' in kwargs:
            influencer.disponibilite_collaboration = kwargs['disponibilite_collaboration']
        
        influencer.save()
        
        # Update selected categories
        category_ids = kwargs.get('selected_categories', [])
        decoded_category_ids = []
        for global_id in category_ids:
            try:
                node_type, category_id = from_global_id(global_id)
                decoded_category_ids.append(int(category_id))
            except Exception:
                try:
                    decoded_category_ids.append(int(global_id))
                except ValueError:
                    raise GraphQLError(f'Invalid category ID: {global_id}')
        
        categories = Category.objects.filter(id__in=decoded_category_ids)
        influencer.selected_categories.set(categories)
        
        # Handle reseaux sociaux
        if 'reseaux_sociaux' in kwargs:
            influencer.reseaux_sociaux.all().delete()
            for rs_data in kwargs['reseaux_sociaux']:
                nombre_abonnes = int(rs_data['nombre_abonnes']) if rs_data.get('nombre_abonnes') else 0
                taux_engagement = float(rs_data['taux_engagement']) if rs_data.get('taux_engagement') else 0.0
                moyenne_vues = int(rs_data.get('moyenne_vues') or 0) if rs_data.get('moyenne_vues') else 0
                moyenne_likes = int(rs_data.get('moyenne_likes') or 0) if rs_data.get('moyenne_likes') else 0
                moyenne_commentaires = int(rs_data.get('moyenne_commentaires') or 0) if rs_data.get('moyenne_commentaires') else 0
                
                ReseauSocial.objects.create(
                    influencer=influencer,
                    plateforme=rs_data['plateforme'],
                    url_profil=rs_data['url_profil'],
                    nombre_abonnes=nombre_abonnes,
                    taux_engagement=taux_engagement,
                    moyenne_vues=moyenne_vues,
                    moyenne_likes=moyenne_likes,
                    moyenne_commentaires=moyenne_commentaires,
                    frequence_publication=rs_data.get('frequence_publication', 'hebdomadaire')
                )
        
        # Handle collaborations
        if 'collaborations' in kwargs:
            influencer.previous_works.all().delete()
            for collab_data in kwargs['collaborations']:
                InfluencerWork.objects.create(
                    influencer=influencer,
                    brand_name=collab_data['nom_marque'],
                    campaign=collab_data['campagne'],
                    period=collab_data['periode'],
                    results=collab_data.get('resultats', ''),
                    publication_link=collab_data.get('lien_publication', '')
                )
        
        # Handle images
        if 'images' in kwargs:
            content_type = ContentType.objects.get_for_model(Influencer)
            influencer.images.all().delete()
            for image_data in kwargs['images']:
                Image.objects.create(
                    content_type=content_type,
                    object_id=influencer.id,
                    url=image_data['url'],
                    is_default=image_data.get('is_default', False),
                    is_public=image_data.get('is_public', True)
                )
        
        # Handle Instagram reels
        if 'selected_reels' in kwargs:
            influencer.instagram_reels.all().delete()
            for reel_data in kwargs['selected_reels']:
                try:
                    taken_at = datetime.fromisoformat(reel_data['taken_at'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    taken_at = datetime.now()
                
                # Truncate post_name to 500 characters to avoid database error
                post_name = reel_data['post_name']
                if len(post_name) > 500:
                    post_name = post_name[:497] + '...'
                
                InstagramReel.objects.create(
                    influencer=influencer,
                    instagram_id=reel_data['id'],
                    code=reel_data['code'],
                    video_url=reel_data['video_url'],
                    thumbnail_url=reel_data['thumbnail_url'],
                    post_name=post_name,
                    duration=reel_data['duration'],
                    taken_at=taken_at,
                    likes=reel_data['likes'],
                    comments=reel_data['comments'],
                    views=reel_data['views'],
                    username=reel_data['username'],
                    hashtags=reel_data.get('hashtags', [])
                )
        
        # Handle Instagram posts
        if 'selected_posts' in kwargs:
            influencer.instagram_posts.all().delete()
            for post_data in kwargs['selected_posts']:
                try:
                    taken_at = datetime.fromisoformat(post_data['taken_at'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    taken_at = datetime.now()
                
                carousel_media = []
                if post_data.get('carousel_media'):
                    carousel_media = [
                        {
                            'id': media['id'],
                            'image_url': media['image_url'],
                            'thumbnail_url': media['thumbnail_url'],
                            'is_video': media['is_video']
                        }
                        for media in post_data['carousel_media']
                    ]
                
                # Truncate post_name to 500 characters to avoid database error
                post_name = post_data['post_name']
                if len(post_name) > 500:
                    post_name = post_name[:497] + '...'
                
                InstagramPost.objects.create(
                    influencer=influencer,
                    instagram_id=post_data['id'],
                    code=post_data['code'],
                    media_type=post_data['media_type'],
                    image_url=post_data['image_url'],
                    thumbnail_url=post_data['thumbnail_url'],
                    post_name=post_name,
                    taken_at=taken_at,
                    likes=post_data['likes'],
                    comments=post_data['comments'],
                    username=post_data['username'],
                    carousel_media=carousel_media,
                    hashtags=post_data.get('hashtags', [])
                )
        
        # Handle portfolio media
        if 'portfolio_media' in kwargs:
            influencer.portfolio_media.all().delete()
            for media_data in kwargs['portfolio_media']:
                try:
                    if media_data.get('date_creation'):
                        date_creation = datetime.strptime(media_data['date_creation'], '%Y-%m-%d').date()
                    else:
                        date_creation = datetime.now().date()
                except ValueError:
                    date_creation = datetime.now().date()
                
                PortfolioMedia.objects.create(
                    influencer=influencer,
                    image_url=media_data['image_url'],
                    titre=media_data['title'],
                    description=media_data.get('description', ''),
                    date_creation=date_creation
                )
        
        # Handle offres collaboration
        if 'offres_collaboration' in kwargs:
            influencer.offres_collaboration.all().delete()
            for offre_data in kwargs['offres_collaboration']:
                OffreCollaboration.objects.create(
                    influencer=influencer,
                    type_collaboration=offre_data['type_collaboration'],
                    tarif_minimum=float(offre_data['tarif_minimum']),
                    tarif_maximum=float(offre_data['tarif_maximum']),
                    conditions=offre_data.get('conditions', '')
                )
        
        # Mark profile as completed
        user.is_completed_profile = True
        user.save(update_fields=['is_completed_profile'])
        
        return CompleteInfluencerProfile(
            influencer=influencer,
            user=user,
            success=True,
            message='Influencer profile completed successfully. Pending admin verification.'
        )
