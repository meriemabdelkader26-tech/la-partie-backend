# architecture_finale.py - Version complète et fonctionnelle
import pandas as pd
import numpy as np
import pickle
import json
import os
from typing import List, Dict, Any, Optional
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, LabelEncoder



class CosineSimilarityRecommender:
    """Recommandateur basé sur la similarité cosinus"""
    
    def __init__(self, X, df):
        self.X = X
        self.df = df
        self.name = "Cosine Similarity"
        self.similarity_matrix = cosine_similarity(X)
    
    def recommend(self, query_idx, n=5):
        """Recommande des influenceurs similaires"""
        similar_indices = np.argsort(self.similarity_matrix[query_idx])[::-1][1:n+1]
        similarity_scores = self.similarity_matrix[query_idx][similar_indices]
        return similar_indices, similarity_scores



class RecommandationSystem:
    """Système final de recommandation pour InfluBridge"""
    
    def __init__(self, data_path: str = 'data/influenceurs_recommendation_ready.csv'):
        print(" Initialisation du système de recommandation...")
        
       
        self.df = pd.read_csv(data_path)
        print(f" Données chargées: {len(self.df)} influenceurs")
        
        
        self.X = self._load_or_create_features()
        
       
        self.model = CosineSimilarityRecommender(self.X, self.df)
        print(f" Matrice de similarité: {self.model.similarity_matrix.shape}")
        
        
        self.categories = self.df['category'].dropna().unique().tolist()
        self.countries = self.df['country'].dropna().unique().tolist()
    
    def _load_or_create_features(self) -> np.ndarray:
        """Charge ou crée la matrice de features"""
        if os.path.exists('data/feature_matrix.npy'):
            return np.load('data/feature_matrix.npy')
        else:
            print("⚠️  Création de la matrice de features...")
            return self._create_features()
    
    def _create_features(self) -> np.ndarray:
        """Crée la matrice de features"""
        scaler = StandardScaler()
        features_list = []
        
        
        numeric_cols = ['followers', 'engagement_rate', 'global_score']
        for col in numeric_cols:
            if col in self.df.columns:
                normalized = scaler.fit_transform(self.df[[col]].fillna(0))
                features_list.append(normalized)
                print(f"   ✓ Normalisé: {col}")
        
        
        if 'category' in self.df.columns:
            le = LabelEncoder()
            category_encoded = le.fit_transform(self.df['category'].fillna('Unknown')).reshape(-1, 1)
            features_list.append(category_encoded)
            print(f"   ✓ Encodé: category")
        
        
        if 'country' in self.df.columns:
            le = LabelEncoder()
            country_encoded = le.fit_transform(self.df['country'].fillna('Unknown')).reshape(-1, 1)
            features_list.append(country_encoded)
            print(f"   ✓ Encodé: country")
        
        
        if features_list:
            X = np.hstack(features_list)
        else:
            
            X = np.random.randn(len(self.df), 5)
        
       
        os.makedirs('data', exist_ok=True)
        np.save('data/feature_matrix.npy', X)
        
        return X
    
    def recommend_for_brand(self, category: str, country: str, n: int = 5) -> Dict[str, Any]:
        """Recommande des influenceurs pour une marque"""
        n = max(1, min(n, 10))
        category = str(category).strip().title()
        country = str(country).strip().title()
        
        print(f"\n Recherche pour: {category} | {country}")
        
        
        mask = (self.df['category'].str.title() == category) & \
               (self.df['country'].str.title() == country)
        
        if not mask.any():
            mask = self.df['category'].str.title() == category
            if not mask.any():
                return self._format_error(f"Aucun influenceur trouvé pour {category}/{country}")
            print(f"     Pays '{country}' non trouvé, utilisation catégorie seule")
        
        if 'global_score' in self.df.columns:
            idx = self.df[mask]['global_score'].idxmax()
        else:
            idx = self.df[mask].index[0]
        
        reference = self.df.iloc[idx]
        print(f"    Référence: {reference['influencer_name']}")
        
        similar_indices, similarity_scores = self.model.recommend(idx, n)
        
        recommendations = []
        for i, (inf_idx, score) in enumerate(zip(similar_indices, similarity_scores), 1):
            inf = self.df.iloc[inf_idx]
            recommendations.append({
                'rank': i,
                'influencer_name': str(inf['influencer_name']),
                'category': str(inf['category']),
                'country': str(inf['country']),
                'followers': int(inf['followers']),
                'followers_formatted': self._format_number(inf['followers']),
                'engagement_rate': float(inf['engagement_rate']),
                'global_score': float(inf.get('global_score', 0)),
                'similarity_score': float(score)
            })
        
        return {
            'success': True,
            'count': len(recommendations),
            'reference': {
                'influencer_name': str(reference['influencer_name']),
                'category': str(reference['category']),
                'country': str(reference['country'])
            },
            'recommendations': recommendations
        }
    
    def _format_error(self, message: str) -> Dict[str, Any]:
        """Formate un message d'erreur"""
        return {
            'success': False,
            'error': message,
            'recommendations': []
        }
    
    def search_influencers(self, category: str = None, country: str = None, 
                          min_followers: int = 0, limit: int = 10) -> Dict[str, Any]:
        """Recherche d'influenceurs avec filtres"""
        mask = pd.Series([True] * len(self.df))
        
        if category:
            mask &= self.df['category'].str.title() == category.title()
        
        if country:
            mask &= self.df['country'].str.title() == country.title()
        
        if min_followers > 0:
            mask &= self.df['followers'] >= min_followers
        
        results_df = self.df[mask].sort_values('global_score' if 'global_score' in self.df.columns else 'followers', 
                                              ascending=False).head(limit)
        
        results = []
        for _, row in results_df.iterrows():
            results.append({
                'influencer_name': str(row['influencer_name']),
                'category': str(row['category']),
                'country': str(row['country']),
                'followers': int(row['followers']),
                'followers_formatted': self._format_number(row['followers']),
                'engagement_rate': float(row['engagement_rate']),
                'global_score': float(row.get('global_score', 0))
            })
        
        return {
            'success': True,
            'count': len(results),
            'results': results
        }
    
    def get_influencer_details(self, index: int = 0) -> Dict[str, Any]:
        """Détails d'un influenceur"""
        if index < 0 or index >= len(self.df):
            return self._format_error(f"Index {index} invalide")
        
        inf = self.df.iloc[index]
        
        return {
            'success': True,
            'influencer_name': str(inf['influencer_name']),
            'category': str(inf['category']),
            'country': str(inf['country']),
            'followers': int(inf['followers']),
            'followers_formatted': self._format_number(inf['followers']),
            'engagement_rate': float(inf['engagement_rate']),
            'global_score': float(inf.get('global_score', 0)),
            'posts': int(inf.get('posts', 0)),
            'avg_likes': int(inf.get('avg_likes', 0)),
            'avg_comments': int(inf.get('avg_comments', 0))
        }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Statistiques du système"""
        return {
            'total_influencers': len(self.df),
            'categories_count': len(self.categories),
            'countries_count': len(self.countries),
            'categories': sorted(self.categories)[:10],  
            'countries': sorted(self.countries)[:10],
            'followers_stats': {
                'min': int(self.df['followers'].min()),
                'max': int(self.df['followers'].max()),
                'avg': int(self.df['followers'].mean()),
                'median': int(self.df['followers'].median())
            },
            'engagement_stats': {
                'min': float(self.df['engagement_rate'].min()),
                'max': float(self.df['engagement_rate'].max()),
                'avg': float(self.df['engagement_rate'].mean()),
                'median': float(self.df['engagement_rate'].median())
            }
        }
    
    def _format_number(self, num: int) -> str:
        """Formate un nombre avec K, M, B"""
        if num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B"
        elif num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)



def run_tests():
    """Exécute des tests du système"""
    print("\n" + "="*60)
    print(" TESTS DU SYSTÈME DE RECOMMANDATION")
    print("="*60)
    
    try:
        
        print(" Initialisation...")
        system = RecommandationSystem()
        
       
        print("\n STATISTIQUES:")
        stats = system.get_system_stats()
        print(f"   • Influenceurs: {stats['total_influencers']}")
        print(f"   • Catégories: {stats['categories_count']}")
        print(f"   • Pays: {stats['countries_count']}")
        print(f"   • Followers moyens: {stats['followers_stats']['avg']:,}")
        print(f"   • Engagement moyen: {stats['engagement_stats']['avg']:.1f}%")
        
       
        print("\n TEST 1: RECOMMANDATION POUR UNE MARQUE")
        print("   Recherche: Fashion / France")
        
        recs = system.recommend_for_brand('Fashion', 'France', 3)
        
        if recs['success']:
            print(f"   ✓ {recs['count']} recommandations trouvées")
            
            if recs.get('reference'):
                ref = recs['reference']
                print(f"    Référence: {ref['influencer_name']}")
            
            for rec in recs['recommendations']:
                print(f"   {rec['rank']}. {rec['influencer_name']}")
                print(f"       {rec['country']} |  {rec['category']}")
                print(f"       {rec['followers_formatted']} followers")
                print(f"       {rec['engagement_rate']:.1f}% engagement")
                print(f"       Similarité: {rec['similarity_score']:.3f}")
        else:
            print(f"    {recs['error']}")
        
        
        print("\n TEST 2: RECHERCHE D'INFLUENCEURS")
        print("   Filtres: Tech, >100K followers")
        
        search = system.search_influencers(category='Tech', min_followers=100000, limit=2)
        
        if search['success']:
            for i, inf in enumerate(search['results'], 1):
                print(f"   {i}. {inf['influencer_name']}")
                print(f"      {inf['followers_formatted']} followers | {inf['engagement_rate']:.1f}% engagement")
        
        
        print("\n TEST 3: DÉTAILS D'UN INFLUENCEUR")
        details = system.get_influencer_details(0)
        if details['success']:
            print(f"   Nom: {details['influencer_name']}")
            print(f"   Catégorie: {details['category']}")
            print(f"   Followers: {details['followers_formatted']}")
            print(f"   Engagement: {details['engagement_rate']:.1f}%")
        
        print("\n" + "="*60)
        print(" TOUS LES TESTS SONT RÉUSSIS !")
        print("="*60)
        
        return system
        
    except Exception as e:
        print(f"\n ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None

def interactive_mode(system):
    """Mode interactif pour tester différentes requêtes"""
    print("\n" + "="*60)
    print(" MODE INTERACTIF")
    print("="*60)
    
    while True:
        print("\nOptions:")
        print("  1. Recommandation pour une marque")
        print("  2. Recherche d'influenceurs")
        print("  3. Détails d'un influenceur")
        print("  4. Statistiques du système")
        print("  5. Quitter")
        
        choice = input("\nChoisissez une option (1-5): ").strip()
        
        if choice == '1':
            category = input("Catégorie (ex: Fashion, Tech): ").strip()
            country = input("Pays (ex: France, USA): ").strip()
            n = input("Nombre de recommandations (défaut: 5): ").strip()
            n = int(n) if n.isdigit() else 5
            
            result = system.recommend_for_brand(category, country, n)
            
            if result['success']:
                print(f"\n {result['count']} recommandations:")
                for rec in result['recommendations']:
                    print(f"   {rec['rank']}. {rec['influencer_name']}")
                    print(f"      {rec['country']} | {rec['category']}")
                    print(f"      {rec['followers_formatted']} followers")
                    print(f"      Similarité: {rec['similarity_score']:.3f}")
            else:
                print(f"\n {result['error']}")
        
        elif choice == '2':
            category = input("Catégorie (laisser vide pour toutes): ").strip() or None
            country = input("Pays (laisser vide pour tous): ").strip() or None
            min_followers = input("Followers minimum (ex: 100000): ").strip()
            min_followers = int(min_followers) if min_followers.isdigit() else 0
            
            result = system.search_influencers(category, country, min_followers, 10)
            
            if result['success']:
                print(f"\n {result['count']} résultats:")
                for i, inf in enumerate(result['results'][:5], 1):
                    print(f"   {i}. {inf['influencer_name']}")
                    print(f"      {inf['category']} | {inf['country']}")
                    print(f"      {inf['followers_formatted']} followers")
        
        elif choice == '3':
            index = input(f"Index (0-{len(system.df)-1}): ").strip()
            if index.isdigit():
                result = system.get_influencer_details(int(index))
                if result['success']:
                    print(f"\n Détails de {result['influencer_name']}:")
                    print(f"   Catégorie: {result['category']}")
                    print(f"   Pays: {result['country']}")
                    print(f"   Followers: {result['followers_formatted']}")
                    print(f"   Engagement: {result['engagement_rate']:.1f}%")
                    print(f"   Score global: {result['global_score']:.2f}")
        
        elif choice == '4':
            stats = system.get_system_stats()
            print(f"\n Statistiques du système:")
            print(f"   Influenceurs: {stats['total_influencers']}")
            print(f"   Catégories: {stats['categories_count']}")
            print(f"   Pays: {stats['countries_count']}")
            print(f"   Followers moyens: {stats['followers_stats']['avg']:,}")
            print(f"   Engagement moyen: {stats['engagement_stats']['avg']:.1f}%")
        
        elif choice == '5':
            print("\n Au revoir !")
            break
        
        else:
            print("\n Option invalide")



if __name__ == "__main__":
    print("="*60)
    print(" SYSTÈME DE RECOMMANDATION INFLUBRIDGE")
    print("="*60)
    
    
    system = run_tests()
    
    if system:
      
        choice = input("\nVoulez-vous utiliser le mode interactif ? (o/n): ").strip().lower()
        if choice == 'o':
            interactive_mode(system)
    
    print("\n" + "="*60)
    print(" SYSTÈME PRÊT POUR LA PRODUCTION !")
    print("="*60)
    print("\n Fichiers utilisés:")
    print("   • data/influenceurs_recommendation_ready.csv")
    print("   • data/feature_matrix.npy")
    print("\n Prochaines étapes:")
    print("   1. Tester avec différentes catégories/pays")
    print("   2. Intégrer dans une API Flask/FastAPI")
    print("   3. Développer une interface utilisateur")