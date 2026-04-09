# api/views.py - VERSION CORRIGÉE
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
from users.influencer_models import Influencer, Image
from users.company_models import Company
from users.influencer_models import InstagramPost, PortfolioMedia
from users.utils import normalize_role
import uuid
import jwt
import json
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, LabelEncoder
import os
import logging
import traceback

# Configure logger
logger = logging.getLogger(__name__)

class HealthCheckView(APIView):
    """Vérification de la santé de l'API"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            'status': 'healthy',
            'service': 'InfluBridge Recommendation API',
            'version': '1.0.0'
        })

class InfluBridgeRecommender:
    """Système de recommandation InfluBridge - VERSION CORRIGÉE"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InfluBridgeRecommender, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if not self.initialized:
            self.initialized = True
            self._initialize()
    
    def _initialize(self):
        """Initialise le système de recommandation"""
        try:
            from django.conf import settings
            logger.info(f"Initializing recommender. BASE_DIR: {settings.BASE_DIR}")
            logger.info(f"Current working directory: {os.getcwd()}")
            
            # Try multiple paths
            possible_paths = [
                os.path.join(settings.BASE_DIR, 'data', 'influenceurs_recommendation_ready.csv'),
                os.path.join(settings.BASE_DIR, 'data', 'influenceurs_clean.csv'),
                os.path.join(settings.BASE_DIR, 'api', 'data', 'influenceurs_recommendation_ready.csv'),
                'data/influenceurs_recommendation_ready.csv',
                'api/data/influenceurs_recommendation_ready.csv',
                '../data/influenceurs_recommendation_ready.csv',
                '/app/data/influenceurs_recommendation_ready.csv',
                '/app/api/data/influenceurs_recommendation_ready.csv'
            ]
            
            # Log all paths being checked
            logger.info(f"Checking {len(possible_paths)} possible data file locations...")
            for i, path in enumerate(possible_paths, 1):
                exists = os.path.exists(path)
                logger.info(f"{i}. {path} - {'FOUND' if exists else 'not found'}")
            
            data_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    data_path = path
                    logger.info(f"✓ Using data file: {data_path}")
                    break
            
            if data_path is None:
                error_msg = f"⚠ CRITICAL: No data file found. Checked {len(possible_paths)} locations."
                logger.error(error_msg)
                logger.error(f"Files in BASE_DIR: {os.listdir(settings.BASE_DIR) if os.path.exists(settings.BASE_DIR) else 'DIR NOT FOUND'}")
                if os.path.exists(os.path.join(settings.BASE_DIR, 'data')):
                    logger.error(f"Files in data/: {os.listdir(os.path.join(settings.BASE_DIR, 'data'))}")
                if os.path.exists(os.path.join(settings.BASE_DIR, 'api', 'data')):
                    logger.error(f"Files in api/data/: {os.listdir(os.path.join(settings.BASE_DIR, 'api', 'data'))}")
                
                self.df = pd.DataFrame()
                self.X = None
                self.similarity_matrix = None
                self.categories = []
                self.countries = []
                return
            
            self.df = pd.read_csv(data_path)
            logger.info(f"✓ Données chargées: {len(self.df)} influenceurs")
            logger.info(f"✓ Columns: {list(self.df.columns)}")
            
            # Créer la matrice de features
            self.X = self._create_feature_matrix()
            logger.info(f"✓ Feature matrix created: {self.X.shape}")
            
            # Calculer la matrice de similarité
            self.similarity_matrix = cosine_similarity(self.X)
            logger.info(f"✓ Matrice de similarité: {self.similarity_matrix.shape}")
            
            # Stocker les valeurs uniques
            self.categories = sorted(self.df['category'].dropna().unique().tolist())
            self.countries = sorted(self.df['country'].dropna().unique().tolist())
            logger.info(f"✓ Categories: {len(self.categories)}, Countries: {len(self.countries)}")
            
        except Exception as e:
            logger.error(f"✗ Erreur d'initialisation: {e}")
            logger.error(f"✗ Traceback: {traceback.format_exc()}")
            raise
    
    def _create_feature_matrix(self):
        """Crée la matrice de features"""
        scaler = StandardScaler()
        features_list = []
        
        # Normaliser les features numériques
        for col in ['followers', 'engagement_rate', 'global_score']:
            if col in self.df.columns:
                normalized = scaler.fit_transform(self.df[[col]].fillna(0))
                features_list.append(normalized)
        
        # Encoder la catégorie
        if 'category' in self.df.columns:
            le = LabelEncoder()
            category_encoded = le.fit_transform(self.df['category'].fillna('Unknown')).reshape(-1, 1)
            features_list.append(category_encoded)
        
        # Encoder le pays
        if 'country' in self.df.columns:
            le = LabelEncoder()
            country_encoded = le.fit_transform(self.df['country'].fillna('Unknown')).reshape(-1, 1)
            features_list.append(country_encoded)
        
        return np.hstack(features_list) if features_list else np.random.randn(len(self.df), 5)
    
    def recommend(self, category, country, n=5):
        """Recommande des influenceurs AVEC FILTRES PAR CATÉGORIE/PAYS"""
        # Check if data is available
        if self.df is None or len(self.df) == 0 or self.similarity_matrix is None:
            return {'error': 'Recommender data not available'}
        
        category = str(category).strip().title()
        country = str(country).strip().title()
        n = max(1, min(n, 20))
        
        # 1. Filtrer par catégorie et pays
        mask = (self.df['category'].str.title() == category) & \
               (self.df['country'].str.title() == country)
        
        if not mask.any():
            mask = self.df['category'].str.title() == category
            if not mask.any():
                return {'error': f'Aucun influenceur trouvé pour {category}/{country}'}
        
        # 2. Get reference influencer
        if 'global_score' in self.df.columns and mask.any():
            idx = self.df[mask]['global_score'].idxmax()
        else:
            idx = self.df[mask].index[0]
        
        reference = self.df.iloc[idx]
        
        # 3. Get ALL similar influencers
        similar_indices = np.argsort(self.similarity_matrix[idx])[::-1][1:]  # Tous sauf lui-même
        similarity_scores = self.similarity_matrix[idx][similar_indices]
        
        # 4. FILTRER pour ne garder que ceux de la même catégorie/pays
        filtered_indices = []
        filtered_scores = []
        
        for inf_idx, score in zip(similar_indices, similarity_scores):
            inf = self.df.iloc[inf_idx]
            # Vérifier si l'influenceur a la même catégorie et pays
            if (str(inf['category']).title() == category and 
                str(inf['country']).title() == country):
                filtered_indices.append(inf_idx)
                filtered_scores.append(score)
                
                # Arrêter quand on a assez de résultats
                if len(filtered_indices) >= n:
                    break
        
        # Si pas assez de résultats avec le filtrage strict, assouplir
        if len(filtered_indices) < n:
            # Accepter juste la même catégorie
            for inf_idx, score in zip(similar_indices, similarity_scores):
                if inf_idx in filtered_indices:
                    continue
                    
                inf = self.df.iloc[inf_idx]
                if str(inf['category']).title() == category:
                    filtered_indices.append(inf_idx)
                    filtered_scores.append(score)
                    
                    if len(filtered_indices) >= n:
                        break
        
        # Si toujours pas assez, prendre les plus similaires tout court
        if len(filtered_indices) < n:
            for inf_idx, score in zip(similar_indices, similarity_scores):
                if inf_idx in filtered_indices:
                    continue
                    
                filtered_indices.append(inf_idx)
                filtered_scores.append(score)
                
                if len(filtered_indices) >= n:
                    break
        
        # 5. Build recommendations
        recommendations = []
        for i, (inf_idx, score) in enumerate(zip(filtered_indices[:n], filtered_scores[:n]), 1):
            inf = self.df.iloc[inf_idx]
            recommendations.append({
                'rank': i,
                'id': int(inf_idx),
                'name': str(inf['influencer_name']),
                'category': str(inf['category']),
                'country': str(inf['country']),
                'followers': int(inf['followers']),
                'followers_formatted': self._format_number(inf['followers']),
                'engagement_rate': float(inf['engagement_rate']),
                'similarity_score': float(score)
            })
        
        return {
            'success': True,
            'query': {'category': category, 'country': country, 'n': n},
            'reference': {
                'id': int(idx),
                'name': str(reference['influencer_name']),
                'category': str(reference['category']),
                'country': str(reference['country'])
            },
            'recommendations': recommendations,
            'total': len(recommendations),
            'note': 'Recommandations filtrées par catégorie/pays' if len(filtered_indices) >= n else 'Filtrage partiel appliqué'
        }
    
    def search(self, category=None, country=None, min_followers=0, limit=10):
        """Recherche d'influenceurs"""
        if self.df is None or len(self.df) == 0:
            return {
                'success': False,
                'results': [],
                'count': 0,
                'error': 'Data not available'
            }
        
        mask = pd.Series([True] * len(self.df))
        
        if category:
            mask &= self.df['category'].str.title() == category.title()
        
        if country:
            mask &= self.df['country'].str.title() == country.title()
        
        if min_followers > 0:
            mask &= self.df['followers'] >= min_followers
        
        results_df = self.df[mask].sort_values('global_score', ascending=False).head(limit)
        
        results = []
        for _, row in results_df.iterrows():
            results.append({
                'id': int(row.name),
                'name': str(row['influencer_name']),
                'category': str(row['category']),
                'country': str(row['country']),
                'followers': int(row['followers']),
                'followers_formatted': self._format_number(row['followers']),
                'engagement_rate': float(row['engagement_rate'])
            })
        
        return {
            'success': True,
            'results': results,
            'count': len(results)
        }
    
    def stats(self):
        """Statistiques du système"""
        if self.df is None or len(self.df) == 0:
            return {
                'total_influencers': 0,
                'categories': [],
                'countries': [],
                'avg_followers': 0,
                'avg_engagement': 0,
                'error': 'Data not available'
            }
        
        return {
            'total_influencers': len(self.df),
            'categories': self.categories,
            'countries': self.countries,
            'avg_followers': int(self.df['followers'].mean()),
            'avg_engagement': float(self.df['engagement_rate'].mean())
        }
    
    def _format_number(self, num):
        """Formate un nombre"""
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)

# Initialize recommender singleton - lazy loading
_recommender_instance = None

def get_recommender():
    """Get or create recommender instance (lazy loading)"""
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = InfluBridgeRecommender()
    return _recommender_instance

class StatsView(APIView):
    """Statistiques du système"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        rec = get_recommender()
        if rec.df is None or len(rec.df) == 0:
            return Response({
                'error': 'Data not available',
                'total_influencers': 0,
                'categories': [],
                'countries': []
            })
        stats = rec.stats()
        return Response(stats)

class CategoriesView(APIView):
    """Liste des catégories"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        rec = get_recommender()
        return Response({
            'categories': rec.categories if rec.categories else [],
            'count': len(rec.categories) if rec.categories else 0
        })

class CountriesView(APIView):
    """Liste des pays"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        rec = get_recommender()
        return Response({
            'countries': rec.countries if hasattr(rec, 'countries') and rec.countries else [],
            'count': len(rec.countries) if hasattr(rec, 'countries') and rec.countries else 0
        })

class RecommendView(APIView):
    """Recommandation d'influenceurs"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        # GET parameters
        category = request.GET.get('category', '')
        country = request.GET.get('country', '')
        n = request.GET.get('n', 5)
        
        logger.info(f"RecommendView GET request: category={category}, country={country}, n={n}")
        
        try:
            n = int(n)
        except:
            n = 5
        
        if not category or not country:
            logger.warning(f"Missing parameters: category={category}, country={country}")
            return Response({
                'error': 'Les paramètres "category" et "country" sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            rec = get_recommender()
            logger.info(f"Recommender instance retrieved. Has data: {rec.df is not None and len(rec.df) > 0 if rec.df is not None else False}")
            
            if rec.df is None or (hasattr(rec.df, '__len__') and len(rec.df) == 0):
                logger.error("Recommender data not available")
                return Response({
                    'error': 'Recommender data not available. Please contact administrator.',
                    'debug_info': 'Data file was not loaded during initialization'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            result = rec.recommend(category, country, n)
            logger.info(f"Recommendation result: {result.get('success', False)}")
            
            if 'error' in result:
                logger.warning(f"Recommendation error: {result['error']}")
                return Response(result, status=status.HTTP_404_NOT_FOUND)
            
            return Response(result)
        except Exception as e:
            logger.error(f"Exception in RecommendView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                'error': 'Recommender service unavailable',
                'detail': str(e),
                'traceback': traceback.format_exc() if os.getenv('DEBUG', 'False') == 'True' else None
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    def post(self, request):
        # POST body
        category = request.data.get('category', '')
        country = request.data.get('country', '')
        n = request.data.get('n', 5)
        
        if not category or not country:
            return Response({
                'error': 'Les champs "category" et "country" sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            rec = get_recommender()
            if rec.df is None or (hasattr(rec.df, '__len__') and len(rec.df) == 0):
                return Response({
                    'error': 'Recommender data not available. Please contact administrator.'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            result = rec.recommend(category, country, n)
            
            if 'error' in result:
                return Response(result, status=status.HTTP_404_NOT_FOUND)
            
            return Response(result)
        except Exception as e:
            return Response({
                'error': 'Recommender service unavailable',
                'detail': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class SearchView(APIView):
    """Recherche d'influenceurs"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        category = request.GET.get('category', '')
        country = request.GET.get('country', '')
        min_followers = request.GET.get('min_followers', 0)
        limit = request.GET.get('limit', 10)
        
        try:
            min_followers = int(min_followers)
            limit = int(limit)
        except:
            min_followers = 0
            limit = 10
        
        rec = get_recommender()
        if rec.df is None or len(rec.df) == 0:
            return Response({
                'results': [],
                'count': 0,
                'message': 'Data not available'
            })
        
        result = rec.search(
            category=category if category else None,
            country=country if country else None,
            min_followers=min_followers,
            limit=limit
        )
        
        return Response(result)

class InfluencerDetailView(APIView):
    """Détails d'un influenceur"""
    permission_classes = [AllowAny]
    
    def get(self, request, influencer_id):
        try:
            influencer_id = int(influencer_id)
        except:
            return Response({'error': 'ID invalide'}, status=status.HTTP_400_BAD_REQUEST)
        
        rec = get_recommender()
        if influencer_id < 0 or influencer_id >= len(rec.df):
            return Response({
                'error': f'ID {influencer_id} invalide. Doit être entre 0 et {len(rec.df)-1}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        inf = rec.df.iloc[influencer_id]
        
        return Response({
            'id': int(influencer_id),
            'name': str(inf['influencer_name']),
            'category': str(inf['category']),
            'country': str(inf['country']),
            'followers': int(inf['followers']),
            'followers_formatted': rec._format_number(inf['followers']),
            'engagement_rate': float(inf['engagement_rate']),
            'global_score': float(inf.get('global_score', 0))
        })


class UploadProfileImageView(APIView):
    """Upload a profile image through REST as a reliable fallback for GraphQL multipart clients."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    allowed_extensions = {'.jpg', '.jpeg', '.png'}
    max_file_size = 5 * 1024 * 1024

    def _parse_bool(self, value, default=False):
        if value is None:
            return default
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _get_user_from_token(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        token = None

        if auth_header:
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0] in {'Bearer', 'JWT', 'Token'}:
                token = parts[1]

        # Fallback for browser-based onboarding flows using cookies.
        if not token:
            token = (
                request.COOKIES.get('JWT')
                or request.COOKIES.get('jwt')
                or request.COOKIES.get('token')
                or request.COOKIES.get('access_token')
                or request.COOKIES.get('accessToken')
            )

        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.PyJWTError:
            return None

        User = get_user_model()
        user_id = payload.get('userId') or payload.get('user_id')
        email = payload.get('email')

        if user_id:
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                return None

        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                return None

        return None

    def _resolve_profile_target(self, user):
        if hasattr(user, 'influencer_profile'):
            return Influencer, user.influencer_profile
        if hasattr(user, 'company_profile'):
            return Company, user.company_profile

        # Create a draft profile during onboarding if it does not exist yet.
        # This prevents step-based uploads from failing before final submit.
        role = normalize_role(getattr(user, 'role', ''))

        if role == 'COMPANY':
            draft_company, _ = Company.objects.get_or_create(
                user=user,
                defaults={'company_name': user.name or user.email}
            )
            return Company, draft_company

        if role == 'INFLUENCER':
            draft_influencer, _ = Influencer.objects.get_or_create(user=user)
            return Influencer, draft_influencer

        return None, None

    def post(self, request):
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else self._get_user_from_token(request)
        if not user:
            return Response({'success': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        file_obj = request.FILES.get('image') or request.FILES.get('file')
        if not file_obj:
            return Response({'success': False, 'message': 'No image file provided. Use field name image.'}, status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(file_obj.name)[1].lower()
        if ext not in self.allowed_extensions:
            return Response({'success': False, 'message': 'Invalid file type. Only PNG/JPG/JPEG are allowed.'}, status=status.HTTP_400_BAD_REQUEST)

        if file_obj.size > self.max_file_size:
            return Response({'success': False, 'message': 'File exceeds 5MB limit.'}, status=status.HTTP_400_BAD_REQUEST)

        model_class, profile_obj = self._resolve_profile_target(user)
        if not profile_obj:
            return Response({'success': False, 'message': 'No influencer or company profile found for this user.'}, status=status.HTTP_400_BAD_REQUEST)

        safe_name = get_valid_filename(file_obj.name)
        file_name = f"{uuid.uuid4().hex}_{safe_name}"
        relative_path = os.path.join('profile_images', str(user.id), file_name).replace('\\\\', '/')
        saved_path = default_storage.save(relative_path, file_obj)
        file_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path.replace('\\\\', '/'))

        is_default = self._parse_bool(request.data.get('is_default'), default=False)
        is_public = self._parse_bool(request.data.get('is_public'), default=True)

        image = Image.objects.create(
            url=file_url,
            is_default=is_default,
            is_public=is_public,
            content_type=ContentType.objects.get_for_model(model_class),
            object_id=profile_obj.id,
        )

        return Response({
            'success': True,
            'message': 'Image uploaded successfully',
            'image': {
                'id': image.id,
                'url': image.url,
                'is_default': image.is_default,
                'is_public': image.is_public,
            }
        }, status=status.HTTP_201_CREATED)


class SelectedInstagramPostsView(APIView):
    """Persist the selected Instagram posts for the current influencer profile."""

    permission_classes = [AllowAny]

    def _get_user_from_token(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        token = None

        if auth_header:
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0] in {'Bearer', 'JWT', 'Token'}:
                token = parts[1]

        # Fallback for browser-based onboarding flows using cookies.
        if not token:
            token = (
                request.COOKIES.get('JWT')
                or request.COOKIES.get('jwt')
                or request.COOKIES.get('token')
                or request.COOKIES.get('access_token')
                or request.COOKIES.get('accessToken')
            )

        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.PyJWTError:
            return None

        User = get_user_model()
        user_id = payload.get('userId') or payload.get('user_id')
        email = payload.get('email')

        if user_id:
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                return None

        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                return None

        return None

    def post(self, request):
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else self._get_user_from_token(request)
        if not user:
            return Response({'success': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            influencer = user.influencer_profile
        except Exception:
            return Response({'success': False, 'message': 'No influencer profile found for this user.'}, status=status.HTTP_400_BAD_REQUEST)

        posts_value = request.data.get('selected_posts')
        if posts_value is None:
            posts_value = request.data.get('posts')

        if not posts_value:
            return Response({'success': False, 'message': 'selected_posts is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(posts_value, str):
            try:
                posts = json.loads(posts_value)
            except json.JSONDecodeError:
                return Response({'success': False, 'message': 'selected_posts must be valid JSON.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            posts = posts_value

        if not isinstance(posts, list):
            return Response({'success': False, 'message': 'selected_posts must be an array.'}, status=status.HTTP_400_BAD_REQUEST)

        influencer.instagram_posts.all().delete()

        saved_posts = []
        for post_data in posts[:6]:
            carousel_media = post_data.get('carousel_media') or []
            if isinstance(carousel_media, str):
                try:
                    carousel_media = json.loads(carousel_media)
                except json.JSONDecodeError:
                    carousel_media = []

            taken_at_value = post_data.get('taken_at') or post_data.get('timestamp')
            if isinstance(taken_at_value, str):
                try:
                    taken_at_value = datetime.fromisoformat(taken_at_value.replace('Z', '+00:00'))
                except ValueError:
                    taken_at_value = datetime.now()
            elif taken_at_value is None:
                taken_at_value = datetime.now()

            post = InstagramPost.objects.create(
                influencer=influencer,
                instagram_id=str(post_data.get('id') or post_data.get('instagram_id') or ''),
                code=str(post_data.get('code') or ''),
                media_type=str(post_data.get('media_type') or 'image'),
                image_url=str(post_data.get('image_url') or post_data.get('thumbnail_url') or ''),
                thumbnail_url=str(post_data.get('thumbnail_url') or post_data.get('image_url') or ''),
                post_name=str(post_data.get('post_name') or post_data.get('caption') or '')[:500],
                taken_at=taken_at_value,
                likes=int(post_data.get('likes') or 0),
                comments=int(post_data.get('comments') or 0),
                username=str(post_data.get('username') or user.name or ''),
                carousel_media=carousel_media,
                hashtags=post_data.get('hashtags') or [],
            )
            saved_posts.append({
                'id': post.id,
                'instagram_id': post.instagram_id,
                'code': post.code,
                'media_type': post.media_type,
                'image_url': post.image_url,
                'thumbnail_url': post.thumbnail_url,
                'post_name': post.post_name,
            })

        return Response({
            'success': True,
            'message': 'Selected posts saved successfully',
            'count': len(saved_posts),
            'posts': saved_posts,
        }, status=status.HTTP_201_CREATED)


class ProfileAssetsView(APIView):
    """Return images, posts and media for step 8/step 2 previews."""

    permission_classes = [AllowAny]

    def _get_user_from_token(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        token = None

        if auth_header:
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0] in {'Bearer', 'JWT', 'Token'}:
                token = parts[1]

        # Fallback for browser-based onboarding flows using cookies.
        if not token:
            token = (
                request.COOKIES.get('JWT')
                or request.COOKIES.get('jwt')
                or request.COOKIES.get('token')
                or request.COOKIES.get('access_token')
                or request.COOKIES.get('accessToken')
            )

        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.PyJWTError:
            return None

        User = get_user_model()
        user_id = payload.get('userId') or payload.get('user_id')
        email = payload.get('email')

        if user_id:
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                return None

        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                return None

        return None

    def get(self, request):
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else self._get_user_from_token(request)
        if not user:
            return Response({'success': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        profile = None
        profile_type = None

        if hasattr(user, 'influencer_profile'):
            profile = user.influencer_profile
            profile_type = 'influencer'
        elif hasattr(user, 'company_profile'):
            profile = user.company_profile
            profile_type = 'company'

        if not profile:
            return Response({'success': False, 'message': 'No profile found for this user.'}, status=status.HTTP_400_BAD_REQUEST)

        images = []
        if hasattr(profile, 'images'):
            images = [
                {
                    'id': image.id,
                    'url': image.url,
                    'is_default': image.is_default,
                    'is_public': image.is_public,
                    'created_at': image.created_at,
                }
                for image in profile.images.all()
            ]

        posts = []
        if profile_type == 'influencer':
            posts = [
                {
                    'id': post.id,
                    'instagram_id': post.instagram_id,
                    'code': post.code,
                    'media_type': post.media_type,
                    'image_url': post.image_url,
                    'thumbnail_url': post.thumbnail_url,
                    'post_name': post.post_name,
                    'taken_at': post.taken_at,
                    'likes': post.likes,
                    'comments': post.comments,
                    'username': post.username,
                    'carousel_media': post.carousel_media,
                    'hashtags': post.hashtags,
                }
                for post in profile.instagram_posts.all().order_by('-taken_at')
            ]

        portfolio_media = []
        if profile_type == 'influencer':
            portfolio_media = [
                {
                    'id': media.id,
                    'image_url': media.image_url,
                    'titre': media.titre,
                    'description': media.description,
                    'date_creation': media.date_creation,
                    'created_at': media.created_at,
                }
                for media in profile.portfolio_media.all().order_by('-date_creation')
            ]

        return Response({
            'success': True,
            'profile_type': profile_type,
            'profile_id': profile.id,
            'images': images,
            'instagram_posts': posts,
            'portfolio_media': portfolio_media,
        })