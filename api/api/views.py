# api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, LabelEncoder
import os

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
    """Système de recommandation InfluBridge"""
    
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
            
            data_path = 'data/influenceurs_recommendation_ready.csv'
            
            if not os.path.exists(data_path):
                
                data_path = '../data/influenceurs_recommendation_ready.csv'
            
            self.df = pd.read_csv(data_path)
            print(f" Données chargées: {len(self.df)} influenceurs")
            
            
            self.X = self._create_feature_matrix()
            
            
            self.similarity_matrix = cosine_similarity(self.X)
            print(f" Matrice de similarité: {self.similarity_matrix.shape}")
            
            
            self.categories = sorted(self.df['category'].dropna().unique().tolist())
            self.countries = sorted(self.df['country'].dropna().unique().tolist())
            
        except Exception as e:
            print(f" Erreur d'initialisation: {e}")
            raise
    
    def _create_feature_matrix(self):
        """Crée la matrice de features"""
        scaler = StandardScaler()
        features_list = []
        
        
        for col in ['followers', 'engagement_rate', 'global_score']:
            if col in self.df.columns:
                normalized = scaler.fit_transform(self.df[[col]].fillna(0))
                features_list.append(normalized)
        
        
        if 'category' in self.df.columns:
            le = LabelEncoder()
            category_encoded = le.fit_transform(self.df['category'].fillna('Unknown')).reshape(-1, 1)
            features_list.append(category_encoded)
        
       
        if 'country' in self.df.columns:
            le = LabelEncoder()
            country_encoded = le.fit_transform(self.df['country'].fillna('Unknown')).reshape(-1, 1)
            features_list.append(country_encoded)
        
        return np.hstack(features_list) if features_list else np.random.randn(len(self.df), 5)
    
    def recommend(self, category, country, n=5):
        """Recommande des influenceurs"""
        category = str(category).strip().title()
        country = str(country).strip().title()
        n = max(1, min(n, 20))
        
        
        mask = (self.df['category'].str.title() == category) & \
               (self.df['country'].str.title() == country)
        
        if not mask.any():
            mask = self.df['category'].str.title() == category
            if not mask.any():
                return {'error': f'Aucun influenceur trouvé pour {category}/{country}'}
        
        
        if 'global_score' in self.df.columns and mask.any():
            idx = self.df[mask]['global_score'].idxmax()
        else:
            idx = self.df[mask].index[0]
        
        reference = self.df.iloc[idx]
        
        
        similar_indices = np.argsort(self.similarity_matrix[idx])[::-1][1:n+1]
        similarity_scores = self.similarity_matrix[idx][similar_indices]
        
        
        recommendations = []
        for i, (inf_idx, score) in enumerate(zip(similar_indices, similarity_scores), 1):
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
            'total': len(recommendations)
        }
    
    def search(self, category=None, country=None, min_followers=0, limit=10):
        """Recherche d'influenceurs"""
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


recommender = InfluBridgeRecommender()

class StatsView(APIView):
    """Statistiques du système"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        stats = recommender.stats()
        return Response(stats)

class CategoriesView(APIView):
    """Liste des catégories"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            'categories': recommender.categories,
            'count': len(recommender.categories)
        })

class CountriesView(APIView):
    """Liste des pays"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            'countries': recommender.countries,
            'count': len(recommender.countries)
        })

class RecommendView(APIView):
    """Recommandation d'influenceurs"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        
        category = request.GET.get('category', '')
        country = request.GET.get('country', '')
        n = request.GET.get('n', 5)
        
        try:
            n = int(n)
        except:
            n = 5
        
        if not category or not country:
            return Response({
                'error': 'Les paramètres "category" et "country" sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = recommender.recommend(category, country, n)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        
        return Response(result)
    
    def post(self, request):
       
        category = request.data.get('category', '')
        country = request.data.get('country', '')
        n = request.data.get('n', 5)
        
        if not category or not country:
            return Response({
                'error': 'Les champs "category" et "country" sont requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = recommender.recommend(category, country, n)
        
        if 'error' in result:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        
        return Response(result)

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
        
        result = recommender.search(
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
        
        if influencer_id < 0 or influencer_id >= len(recommender.df):
            return Response({
                'error': f'ID {influencer_id} invalide. Doit être entre 0 et {len(recommender.df)-1}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        inf = recommender.df.iloc[influencer_id]
        
        return Response({
            'id': int(influencer_id),
            'name': str(inf['influencer_name']),
            'category': str(inf['category']),
            'country': str(inf['country']),
            'followers': int(inf['followers']),
            'followers_formatted': recommender._format_number(inf['followers']),
            'engagement_rate': float(inf['engagement_rate']),
            'global_score': float(inf.get('global_score', 0))
        })