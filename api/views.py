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
from offer.models import Offer
from .recommendation_service import get_hybrid_recommender
import uuid
import jwt
import json
import requests
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, LabelEncoder
import os
import logging
import traceback
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Configure logger
logger = logging.getLogger(__name__)

class RapidAPIHandler:
    """Helper to interact with Instagram RapidAPI"""
    
    @staticmethod
    def get_headers():
        return {
            "Content-Type": "application/json",
            "x-rapidapi-key": os.getenv('INSTAGRAM_RAPIDAPI_KEY'),
            "x-rapidapi-host": os.getenv('INSTAGRAM_RAPIDAPI_HOST', 'instagram120.p.rapidapi.com'),
        }

    @staticmethod
    def fetch_user_info(username):
        """Fetch real-time user info from RapidAPI"""
        # Using a longer timeout for trending fetch if needed
        base_url = os.getenv('INSTAGRAM_RAPIDAPI_URL', 'https://instagram120.p.rapidapi.com/api/instagram').rstrip('/')
        base_url = base_url.replace('/userInfo', '')
        endpoint_url = f"{base_url}/userInfo"
        
        # Add caching
        from django.core.cache import cache
        cache_key = f"ig_user_info_{username}"
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Using cached real-time data for @{username}...")
            return cached_data
            
        headers = RapidAPIHandler.get_headers()
        payload = {"username": username}
        
        try:
            logger.info(f"Fetching real-time data for @{username}...")
            response = requests.post(endpoint_url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and len(data['result']) > 0:
                    user_data = data['result'][0].get('user', {})
                    
                    profile_pic = user_data.get('profile_pic_url_hd') or user_data.get('hd_profile_pic_url_info', {}).get('url') or user_data.get('profile_pic_url')
                    if profile_pic and 's150x150' in profile_pic:
                        profile_pic = profile_pic.replace('s150x150', 's1080x1080')
                    
                    result_data = {
                        'name': user_data.get('full_name'),
                        'username': user_data.get('username'),
                        'followers': user_data.get('follower_count'),
                        'following': user_data.get('following_count'),
                        'posts_count': user_data.get('media_count'),
                        'profile_pic': profile_pic,
                        'is_verified': user_data.get('is_verified'),
                        'biography': user_data.get('biography'),
                        'external_url': user_data.get('external_url'),
                        'profile_url': f"https://www.instagram.com/{user_data.get('username')}/",
                        'is_realtime': True
                    }
                    
                    # Cache for 24 hours
                    cache.set(cache_key, result_data, timeout=60*60*24)
                    return result_data
            logger.warning(f"Failed to fetch real-time data for @{username}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching real-time data for @{username}: {str(e)}")
        
        return None

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

class TrendingInfluencersView(APIView):
    """View to get live trending influencers using RapidAPI"""
    permission_classes = [AllowAny]
    
    # Predefined list of top influencers for trending demo
    TOP_USERNAMES = [
        'cristiano', 'leomessi', 'selenagomez', 'kyliejenner', 
        'therock', 'arianagrande', 'kimkardashian', 'beyonce',
        'khloekardashian', 'justinbieber', 'kendalljenner', 'nike'
    ]

    @method_decorator(cache_page(60 * 60)) # Cache for 1 hour
    def get(self, request):
        category = request.GET.get('category')
        country = request.GET.get('country')
        limit = int(request.GET.get('n', 6))
        
        # In a real app, we might use the category/country to filter our trending list
        # For now, we fetch a subset of top influencers
        results = []
        
        # To avoid hitting API limits too hard in a single request, we could use a cache
        # or just fetch a few. For this demo, we'll fetch the first 'limit' users.
        target_usernames = self.TOP_USERNAMES[:limit]
        
        # If we have filters, we might want to use our CSV data to find usernames 
        # matching those filters and then fetch their real-time data.
        if category or country:
            rec = get_recommender()
            if rec.df is not None and len(rec.df) > 0:
                mask = pd.Series([True] * len(rec.df))
                if category:
                    mask &= rec.df['category'].str.title() == category.title()
                if country:
                    mask &= rec.df['country'].str.title() == country.title()
                
                filtered_usernames = rec.df[mask].sort_values('global_score', ascending=False)['username'].dropna().unique().tolist()
                if filtered_usernames:
                    target_usernames = filtered_usernames[:limit]

        for username in target_usernames:
            # Check cache if implemented, or just fetch
            data = RapidAPIHandler.fetch_user_info(username)
            if data:
                # Add some synthetic "trending" metrics if not available
                data['engagement_rate'] = round(np.random.uniform(1.5, 8.5), 2)
                results.append(data)
            else:
                # Fallback to CSV data if API fails
                rec = get_recommender()
                if rec.df is not None and 'username' in rec.df.columns:
                    match = rec.df[rec.df['username'] == username]
                    if not match.empty:
                        row = match.iloc[0]
                        results.append({
                            'name': row['influencer_name'],
                            'username': username,
                            'followers': int(row['followers']),
                            'followers_formatted': rec._format_number(row['followers']),
                            'category': row['category'],
                            'country': row['country'],
                            'engagement_rate': float(row['engagement_rate']),
                            'profile_url': f"https://www.instagram.com/{username}/",
                            'is_realtime': False
                        })

        return Response({
            'success': True,
            'count': len(results),
            'recommendations': results # Keep key name for frontend compatibility if needed
        })

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
                'similarity_score': float(score),
                'is_realtime': False
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
    
    @method_decorator(cache_page(60 * 60)) # Cache for 1 hour
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
    """Recherche d'influenceurs - AVEC SUPPORT TEMPS RÉEL RAPIDAPI"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        username_query = request.GET.get('username', '')
        category = request.GET.get('category', '')
        country = request.GET.get('country', '')
        min_followers = request.GET.get('min_followers', 0)
        limit = request.GET.get('limit', 10)
        
        # 1. Option Temps Réel : Recherche par username via RapidAPI
        if username_query:
            realtime_data = RapidAPIHandler.fetch_user_info(username_query)
            if realtime_data:
                return Response({
                    'success': True,
                    'results': [{
                        'id': -1, # Signifie hors-base CSV
                        'name': realtime_data['name'],
                        'username': realtime_data['username'],
                        'category': 'Unknown',
                        'country': 'Unknown',
                        'followers': realtime_data['followers'],
                        'followers_formatted': get_recommender()._format_number(realtime_data['followers']),
                        'engagement_rate': 0, # Nécessiterait plus d'appels API
                        'profile_pic': realtime_data['profile_pic'],
                        'is_realtime': True
                    }],
                    'count': 1,
                    'source': 'RapidAPI (Real-time)'
                })

        # 2. Fallback ou Recherche Classique : Utilisation du CSV
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
        
        # Ajouter le flag is_realtime aux résultats CSV
        if 'results' in result:
            for item in result['results']:
                item['is_realtime'] = False
        
        result['source'] = 'CSV Database'
        return Response(result)

class InfluencerDetailView(APIView):
    """Détails d'un influenceur - AVEC DONNÉES TEMPS RÉEL OPTIONNELLES"""
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
        username = inf.get('username')
        
        # Base data from CSV
        data = {
            'id': int(influencer_id),
            'name': str(inf['influencer_name']),
            'username': str(username) if username else None,
            'category': str(inf['category']),
            'country': str(inf['country']),
            'followers': int(inf['followers']),
            'followers_formatted': rec._format_number(inf['followers']),
            'engagement_rate': float(inf['engagement_rate']),
            'global_score': float(inf.get('global_score', 0)),
            'is_realtime': False
        }
        
        # Try to get real-time data if username is available
        if username:
            realtime_data = RapidAPIHandler.fetch_user_info(username)
            if realtime_data:
                # Update with fresh data
                data.update({
                    'name': realtime_data['name'] or data['name'],
                    'followers': realtime_data['followers'],
                    'followers_formatted': rec._format_number(realtime_data['followers']),
                    'posts_count': realtime_data['posts_count'],
                    'profile_pic': realtime_data['profile_pic'],
                    'is_verified': realtime_data['is_verified'],
                    'biography': realtime_data['biography'],
                    'external_url': realtime_data['external_url'],
                    'is_realtime': True
                })
        
        return Response(data)


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


class InstagramScraperView(APIView):
    """
    Scrape Instagram posts or reels for a given username using RapidAPI.
    Moved from frontend to backend for better security and control.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        scrape_type = request.data.get('type', 'posts') # 'posts' or 'reels'

        if not username:
            return Response({
                'success': False, 
                'message': 'Username is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if scrape_type not in ['posts', 'reels']:
            return Response({
                'success': False,
                'message': 'Invalid type. Use "posts" or "reels".'
            }, status=status.HTTP_400_BAD_REQUEST)

        rapidapi_url = os.getenv('INSTAGRAM_RAPIDAPI_URL', 'https://instagram120.p.rapidapi.com/api/instagram')
        rapidapi_key = os.getenv('INSTAGRAM_RAPIDAPI_KEY')
        rapidapi_host = os.getenv('INSTAGRAM_RAPIDAPI_HOST', 'instagram120.p.rapidapi.com')

        if not rapidapi_key:
            return Response({
                'success': False,
                'message': 'Instagram API key not configured on backend.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Normalize URL: ensure it doesn't end with / and doesn't have /userInfo
        base_url = rapidapi_url.rstrip('/').replace('/userInfo', '')
        endpoint_url = f"{base_url}/{scrape_type}"

        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-key": rapidapi_key,
            "x-rapidapi-host": rapidapi_host,
        }

        payload = {
            "username": username,
            "maxId": ""
        }

        try:
            logger.info(f"Scraping Instagram {scrape_type} for @{username}...")
            response = requests.post(endpoint_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"RapidAPI error {response.status_code}: {response.text}")
                # Return empty list as frontend did for common errors
                if response.status_code in [400, 404, 405, 422]:
                    return Response({
                        'success': True,
                        'count': 0,
                        'items': []
                    })
                
                return Response({
                    'success': False,
                    'message': f"External API error: {response.status_code}"
                }, status=status.HTTP_502_BAD_GATEWAY)

            data = response.json()
            raw_items = self._to_raw_items(data)
            
            # If reels returned nothing, try posts as a fallback (matching frontend behavior)
            if not raw_items and scrape_type == 'reels':
                logger.info(f"No reels found for @{username}, falling back to posts...")
                fallback_url = f"{base_url}/posts"
                fb_response = requests.post(fallback_url, json=payload, headers=headers, timeout=30)
                if fb_response.status_code == 200:
                    raw_items = self._to_raw_items(fb_response.json())

            return Response({
                'success': True,
                'count': len(raw_items),
                'items': raw_items
            })

        except requests.exceptions.RequestException as e:
            logger.error(f"Request to RapidAPI failed: {str(e)}")
            return Response({
                'success': False,
                'message': 'Failed to connect to Instagram API service.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"Unexpected error during Instagram scraping: {str(e)}")
            return Response({
                'success': False,
                'message': 'An internal error occurred during scraping.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _to_raw_items(self, payload):
        """Ported normalization logic from frontend to_raw_items function."""
        if not payload:
            return []

        # 1. Format direct (data.items ou items)
        direct_items = None
        if isinstance(payload, dict):
            direct_items = payload.get('data', {}).get('items') or payload.get('items')
        
        if isinstance(direct_items, list) and len(direct_items) > 0:
            return [item.get('node', {}).get('media') or item.get('node') or item for item in direct_items]

        # 2. Format edges (data.edges ou edges)
        edges = []
        if isinstance(payload, dict):
            edges = payload.get('data', {}).get('edges') or payload.get('edges') or []
        
        edge_items = []
        if isinstance(edges, list):
            for edge in edges:
                if isinstance(edge, dict) and edge.get('node'):
                    edge_items.append(edge.get('node'))
        
        if edge_items:
            return [item.get('media') or item for item in edge_items]

        # 3. Format result.edges[].node ou result.edges[].node.media
        result = payload.get('result', {}) if isinstance(payload, dict) else {}
        if isinstance(result, dict) and isinstance(result.get('edges'), list) and len(result['edges']) > 0:
            items = []
            for edge in result['edges']:
                if isinstance(edge, dict):
                    items.append(edge.get('node', {}).get('media') or edge.get('node'))
            return [i for i in items if i]

        # 4. Format result.data.items, result.items, result.posts
        if isinstance(result, dict):
            candidates = [
                result.get('data', {}).get('items') if isinstance(result.get('data'), dict) else None,
                result.get('items'),
                result.get('posts'),
                result if isinstance(result, list) else None
            ]
            for candidate in candidates:
                if isinstance(candidate, list) and len(candidate) > 0:
                    return [item.get('node', {}).get('media') or item.get('node') or item for item in candidate]

        return []

class GenerateBioView(APIView):
    """
    Generate or refine an Instagram biography using LangChain and Gemini 2.5 Flash Lite.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        prompt = request.data.get('prompt', '').strip()
        
        if not prompt:
            return Response({
                'success': False,
                'message': 'Prompt is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return Response({
                'success': False,
                'message': 'Gemini API key not configured on backend.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            # Using Gemini 2.5 Flash Lite via Langchain
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                google_api_key=api_key,
                temperature=0.7,
                max_output_tokens=150
            )

            messages = [
                SystemMessage(content=(
                    "You are an expert personal branding assistant for social media influencers. "
                    "Your task is to take the user's input and write a professional, engaging, and concise Instagram/social media biography. "
                    "Keep it under 150 characters if possible, use appropriate emojis, and make it sound authentic. "
                    "Do not include quotes or any conversational filler like 'Here is your bio:', just return the final biography text."
                )),
                HumanMessage(content=f"Please refine or generate a bio based on this input: {prompt}")
            ]

            response = llm.invoke(messages)
            
            return Response({
                'success': True,
                'bio': response.content.strip()
            })

        except Exception as e:
            logger.error(f"Error generating bio with Gemini: {str(e)}")
            return Response({
                'success': False,
                'message': f"Failed to generate bio: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RefineOfferConditionsView(APIView):
    """
    Refine influencer collaboration offer conditions using Gemini.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        conditions = request.data.get('conditions', '').strip()
        
        if not conditions:
            return Response({
                'success': False,
                'message': 'Conditions text is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return Response({
                'success': False,
                'message': 'Gemini API key not configured on backend.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            # Using Gemini 2.5 Flash Lite via Langchain
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                google_api_key=api_key,
                temperature=0.7,
                max_output_tokens=300
            )

            messages = [
                SystemMessage(content=(
                    "You are an expert talent manager and legal assistant for social media influencers. "
                    "Your task is to take the user's rough notes for a collaboration offer's conditions/requirements "
                    "and rewrite them into a professional, clear, and structured format. "
                    "Use bullet points if appropriate. Ensure the tone is professional, protecting the influencer's rights "
                    "while being appealing to brands. "
                    "Do not include conversational filler like 'Here are the refined conditions:', just return the final text."
                )),
                HumanMessage(content=f"Please refine these offer conditions: {conditions}")
            ]

            response = llm.invoke(messages)
            
            return Response({
                'success': True,
                'refined_conditions': response.content.strip()
            })

        except Exception as e:
            logger.error(f"Error refining conditions with Gemini: {str(e)}")
            return Response({
                'success': False,
                'message': f"Failed to refine conditions: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CheckUrlView(APIView):
    """
    Check if a given URL is reachable.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        url = request.data.get('url', '').strip()
        
        if not url:
            return Response({
                'success': False,
                'message': 'URL is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'https://' + url

        try:
            # Add a timeout and a user-agent to avoid being blocked by some servers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
            
            if response.status_code < 400:
                return Response({
                    'success': True,
                    'message': 'URL is reachable'
                })
            else:
                return Response({
                    'success': False,
                    'message': f'URL returned status code {response.status_code}'
                })
        except requests.exceptions.RequestException as e:
            return Response({
                'success': False,
                'message': f'Could not reach URL: {str(e)}'
            })

class FetchSocialStatsView(APIView):
    """
    Fetch statistics for various social media platforms (TikTok, YouTube, Twitter, etc.)
    using RapidAPI endpoints.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        platform = request.data.get('platform', '').lower()
        url = request.data.get('url', '').strip()

        if not platform or not url:
            return Response({
                'success': False,
                'message': 'Platform and URL are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Extract username from URL (basic extraction)
        username = url.rstrip('/').split('/')[-1]
        if '?' in username:
            username = username.split('?')[0]
        if username.startswith('@'):
            username = username[1:]

        try:
            stats = {
                'followers': '0',
                'engagement_rate': '0',
                'avg_views': '0',
                'avg_likes': '0',
                'avg_comments': '0'
            }

            if platform == 'tiktok':
                # Using TokAPI (Mobile Version) or similar TikTok API on RapidAPI
                api_key = os.getenv('TIKTOK_RAPIDAPI_KEY')
                api_host = os.getenv('TIKTOK_RAPIDAPI_HOST', 'tiktok-api23.p.rapidapi.com')
                if not api_key:
                    raise Exception("TikTok RapidAPI key not configured.")
                
                headers = {
                    "x-rapidapi-key": api_key,
                    "x-rapidapi-host": api_host
                }
                response = requests.get(f"https://{api_host}/api/user/info?uniqueId={username}", headers=headers, timeout=15)
                logger.info(f"TikTok API Response ({response.status_code}): {response.text[:1000]}")
                if response.status_code == 200:
                    data = response.json()
                    
                    # New API structure uses 'userInfo' instead of 'data'
                    user_info = data.get('userInfo', {})
                    
                    # Stats are nested under 'stats'
                    user_stats = user_info.get('stats', {})
                    stats['followers'] = str(user_stats.get('followerCount', 0))
                    stats['avg_likes'] = str(user_stats.get('heartCount', 0)) # Total likes
                    stats['engagement_rate'] = "0"
                    
                    # Add profile info
                    user_details = user_info.get('user', {})
                    stats['profile_pic'] = user_details.get('avatarLarger') or user_details.get('avatarMedium') or user_details.get('avatarThumb') or ""
                    stats['name'] = user_details.get('nickname') or ""
                    stats['biography'] = user_details.get('signature') or ""
                else:
                    raise Exception(f"TikTok API Error: {response.text}")
            
            elif platform == 'youtube':
                # Using YouTube v3 API on RapidAPI
                api_key = os.getenv('YOUTUBE_RAPIDAPI_KEY')
                api_host = os.getenv('YOUTUBE_RAPIDAPI_HOST', 'youtube-v31.p.rapidapi.com')
                if not api_key:
                    raise Exception("YouTube RapidAPI key not configured.")
                
                headers = {
                    "x-rapidapi-key": api_key,
                    "x-rapidapi-host": api_host
                }
                # First get channel ID from username/handle
                search_res = requests.get(f"https://{api_host}/search?q={username}&part=snippet,id&type=channel", headers=headers, timeout=15)
                logger.info(f"YouTube Search API Response ({search_res.status_code}): {search_res.text[:1000]}")
                if search_res.status_code == 200 and search_res.json().get('items'):
                    channel_id = search_res.json()['items'][0]['id']['channelId']
                    
                    # Then get channel stats
                    channel_res = requests.get(f"https://{api_host}/channels?part=statistics&id={channel_id}", headers=headers, timeout=15)
                    logger.info(f"YouTube Channel API Response ({channel_res.status_code}): {channel_res.text[:1000]}")
                    if channel_res.status_code == 200 and channel_res.json().get('items'):
                        channel_data = channel_res.json()['items'][0]
                        statistics = channel_data['statistics']
                        stats['followers'] = str(statistics.get('subscriberCount', 0))
                        stats['avg_views'] = str(statistics.get('viewCount', 0)) # Total views
                        
                        # Add profile info
                        snippet = channel_data.get('snippet', {})
                        stats['name'] = snippet.get('title', '')
                        stats['biography'] = snippet.get('description', '')
                        stats['profile_pic'] = snippet.get('thumbnails', {}).get('high', {}).get('url') or snippet.get('thumbnails', {}).get('default', {}).get('url') or ""
                    else:
                        raise Exception(f"YouTube Channel API Error: {channel_res.text}")
                else:
                    raise Exception(f"YouTube Search API Error: {search_res.text}")
            
            elif platform == 'twitter':
                # Using Twitter API on RapidAPI
                api_key = os.getenv('TWITTER_RAPIDAPI_KEY')
                api_host = os.getenv('TWITTER_RAPIDAPI_HOST', 'twitter-api45.p.rapidapi.com')
                if not api_key:
                    raise Exception("Twitter RapidAPI key not configured.")
                
                headers = {
                    "x-rapidapi-key": api_key,
                    "x-rapidapi-host": api_host
                }
                response = requests.get(f"https://{api_host}/screenname.php?screenname={username}", headers=headers, timeout=15)
                logger.info(f"Twitter API Response ({response.status_code}): {response.text[:1000]}")
                if response.status_code == 200:
                    data = response.json()
                    # Added fallbacks for different possible Twitter API response keys
                    stats['followers'] = str(data.get('sub_count', data.get('followers', data.get('follower_count', 0))))
                    stats['avg_views'] = str(data.get('statuses_count', 0)) # Mapping Tweets to avg_views
                    stats['avg_likes'] = str(data.get('friends', 0)) # Mapping Following to avg_likes
                    
                    # Add profile info
                    stats['name'] = data.get('name', '')
                    stats['biography'] = data.get('desc', data.get('description', ''))
                    profile_pic = data.get('avatar', data.get('profile_image_url_https', ''))
                    if profile_pic and '_normal' in profile_pic:
                        profile_pic = profile_pic.replace('_normal', '_400x400')
                    stats['profile_pic'] = profile_pic
                else:
                    raise Exception(f"Twitter API Error: {response.text}")
            
            elif platform == 'facebook':
                # Using Facebook API on RapidAPI
                api_key = os.getenv('FACEBOOK_RAPIDAPI_KEY')
                api_host = os.getenv('FACEBOOK_RAPIDAPI_HOST', 'facebook-scraper3.p.rapidapi.com')
                if not api_key:
                    raise Exception("Facebook RapidAPI key not configured.")
                
                headers = {
                    "x-rapidapi-key": api_key,
                    "x-rapidapi-host": api_host
                }
                import urllib.parse
                encoded_url = urllib.parse.quote(url)
                response = requests.get(f"https://{api_host}/page/details?url={encoded_url}", headers=headers, timeout=15)
                logger.info(f"Facebook API Response ({response.status_code}): {response.text[:1000]}")
                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', {})
                    
                    stats['followers'] = str(results.get('followers') or 0)
                    stats['avg_likes'] = str(results.get('likes') or 0)
                    
                    # Add profile info
                    stats['name'] = results.get('name', '')
                    stats['biography'] = results.get('intro', '')
                    stats['profile_pic'] = results.get('image', '')
                else:
                    raise Exception(f"Facebook API Error: {response.text}")
            
            elif platform == 'linkedin':
                # Using LinkedIn API on RapidAPI
                api_key = os.getenv('LINKEDIN_RAPIDAPI_KEY')
                api_host = os.getenv('LINKEDIN_RAPIDAPI_HOST', 'unlimited-linkedin-scraper.p.rapidapi.com')
                if not api_key:
                    raise Exception("LinkedIn RapidAPI key not configured.")
                
                headers = {
                    "x-rapidapi-key": api_key,
                    "x-rapidapi-host": api_host
                }
                import urllib.parse
                encoded_url = urllib.parse.quote(url)
                response = requests.get(f"https://{api_host}/api/linkedin/profile?url={encoded_url}&use_cache=false&maximum_cache_age=3600", headers=headers, timeout=15)
                logger.info(f"LinkedIn API Response ({response.status_code}): {response.text[:1000]}")
                if response.status_code == 200:
                    data = response.json()
                    stats['followers'] = str(data.get('followers', 0))
                    stats['avg_likes'] = str(data.get('connections', '0')) # Mapping connections to avg_likes
                    
                    # Add profile info
                    stats['name'] = data.get('name', '')
                    stats['biography'] = data.get('about', '')
                    stats['profile_pic'] = data.get('image', '')
                else:
                    raise Exception(f"LinkedIn API Error: {response.text}")
            
            elif platform == 'snapchat':
                # Snapchat APIs are rare on RapidAPI, fallback to mock or basic implementation
                api_key = os.getenv('SNAPCHAT_RAPIDAPI_KEY')
                if not api_key:
                    raise Exception("Snapchat RapidAPI key not configured.")
                # Add implementation here if you find a specific Snapchat API
                pass
            
            else:
                raise Exception(f"Platform {platform} is not currently supported for auto-fetching.")

            return Response({
                'success': True,
                'platform': platform,
                'username': username,
                'stats': stats
            })

        except Exception as e:
            logger.error(f"Error fetching {platform} stats: {str(e)}")
            return Response({
                'success': False,
                'message': f"Failed to fetch statistics: {str(e)}. Make sure you have configured the RapidAPI keys in your .env file."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RecommendationBaseView(APIView):
    """Base class for recommendation views with token support."""
    
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

class PersonalizedOffersView(RecommendationBaseView):
    """View to get recommended offers for the logged-in influencer."""
    permission_classes = [AllowAny]

    def get(self, request, influencer_id=None):
        user = self._get_user_from_token(request)
        
        if influencer_id is None and user:
            if hasattr(user, 'influencer_profile'):
                influencer_id = user.influencer_profile.id
            else:
                return Response({'error': 'User is not an influencer'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Fallback for testing if not provided in URL and no user
        if influencer_id is None:
            influencer_id = request.GET.get('influencer_id')
            
        if not influencer_id:
            return Response({'error': 'Influencer ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            recommender = get_hybrid_recommender()
            recommendations = recommender.recommend_offers_for_influencer(int(influencer_id))
            return Response({
                'success': True,
                'influencer_id': influencer_id,
                'recommendations': recommendations
            })
        except Exception as e:
            logger.error(f"Recommendation error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OfferRecommendationsView(RecommendationBaseView):
    """View to get recommended influencers for a specific offer."""
    permission_classes = [AllowAny]

    def get(self, request, offer_id):
        if not offer_id:
            return Response({'error': 'Offer ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            recommender = get_hybrid_recommender()
            recommendations = recommender.recommend_influencers_for_offer(int(offer_id))
            return Response({
                'success': True,
                'offer_id': offer_id,
                'recommendations': recommendations
            })
        except Exception as e:
            logger.error(f"Recommendation error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
