# eda_analysis.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
import warnings
warnings.filterwarnings('ignore')

# Configuration
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

# Connexion à PostgreSQL
engine = create_engine('postgresql://postgres:0000@localhost:5432/influBridge')

def load_data():
    """Charge les données depuis PostgreSQL"""
    df = pd.read_sql("SELECT * FROM influenceurs_simple", engine)
    print(f"✅ Données chargées: {df.shape[0]} lignes, {df.shape[1]} colonnes")
    return df

def basic_statistics(df):
    """Statistiques descriptives basiques"""
    print("="*60)
    print("📊 STATISTIQUES DESCRIPTIVES")
    print("="*60)
    
    # Statistiques numériques
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    print("\n📈 Statistiques des variables numériques:")
    print(df[numeric_cols].describe())
    
    # Variables catégorielles
    categorical_cols = ['category', 'country']
    print("\n🏷️ Distribution des catégories:")
    for col in categorical_cols:
        if col in df.columns:
            print(f"\n{col}:")
            print(df[col].value_counts().head(10))
            print(f"Valeurs uniques: {df[col].nunique()}")

def feature_engineering(df):
    """Création de nouvelles features pour le ML"""
    print("\n" + "="*60)
    print("🔧 FEATURE ENGINEERING")
    print("="*60)
    
    df_eng = df.copy()
    
    # 1. Ratio d'engagement par follower
    df_eng['engagement_per_follower'] = df_eng['engagement_rate'] / df_eng['followers']
    
    # 2. Log transformation pour les followers (souvent skewed)
    df_eng['log_followers'] = np.log1p(df_eng['followers'])
    
    # 3. Ratio likes/comments
    df_eng['likes_comments_ratio'] = df_eng['avg_likes'] / (df_eng['avg_comments'] + 1)
    
    # 4. Popularity score (combinaison de plusieurs métriques)
    df_eng['popularity_score'] = (
        (df_eng['followers'] / df_eng['followers'].max()) * 0.4 +
        (df_eng['engagement_rate'] / df_eng['engagement_rate'].max()) * 0.3 +
        (df_eng['avg_likes'] / df_eng['avg_likes'].max()) * 0.2 +
        (df_eng['posts'] / df_eng['posts'].max()) * 0.1
    )
    
    # 5. Catégories d'audience
    df_eng['audience_size_category'] = pd.cut(
        df_eng['followers'],
        bins=[0, 10000, 100000, 1000000, 10000000, float('inf')],
        labels=['Micro', 'Nano', 'Mid', 'Macro', 'Mega']
    )
    
    print(f"✅ {len(df_eng.columns) - len(df.columns)} nouvelles features créées")
    return df_eng

def correlation_analysis(df):
    """Analyse des corrélations"""
    print("\n" + "="*60)
    print("🔗 ANALYSE DES CORRÉLATIONS")
    print("="*60)
    
    # Matrice de corrélation
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    corr_matrix = df[numeric_cols].corr()
    
    plt.figure(figsize=(12, 8))
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0, 
                square=True, linewidths=.5, cbar_kws={"shrink": .8})
    plt.title('Matrice de Corrélation', fontsize=16, pad=20)
    plt.tight_layout()
    plt.savefig('correlation_matrix.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Corrélations fortes avec followers
    print("\n🎯 Corrélations avec 'followers':")
    followers_corr = corr_matrix['followers'].sort_values(ascending=False)
    for feature, corr in followers_corr.items():
        if feature != 'followers' and abs(corr) > 0.3:
            print(f"  {feature}: {corr:.3f}")

def visualize_distributions(df):
    """Visualisations des distributions"""
    print("\n" + "="*60)
    print("📊 VISUALISATION DES DISTRIBUTIONS")
    print("="*60)
    
    # 1. Distribution des followers
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # Followers (log scale)
    axes[0, 0].hist(df['followers'], bins=50, edgecolor='black', alpha=0.7)
    axes[0, 0].set_title('Distribution des Followers')
    axes[0, 0].set_xlabel('Followers')
    axes[0, 0].set_ylabel('Fréquence')
    axes[0, 0].set_xscale('log')
    
    # Engagement rate
    axes[0, 1].hist(df['engagement_rate'], bins=30, edgecolor='black', alpha=0.7, color='pink')
    axes[0, 1].set_title('Distribution du Taux d\'Engagement')
    axes[0, 1].set_xlabel('Engagement Rate (%)')
    axes[0, 1].set_ylabel('Fréquence')
    
    # Posts
    axes[0, 2].hist(df['posts'], bins=30, edgecolor='black', alpha=0.7, color='orange')
    axes[0, 2].set_title('Distribution des Posts')
    axes[0, 2].set_xlabel('Nombre de Posts')
    axes[0, 2].set_ylabel('Fréquence')
    
    # Boxplot par catégorie
    top_categories = df['category'].value_counts().head(8).index
    df_top_cat = df[df['category'].isin(top_categories)]
    
    sns.boxplot(data=df_top_cat, x='category', y='followers', ax=axes[1, 0])
    axes[1, 0].set_title('Followers par Catégorie')
    axes[1, 0].set_xticklabels(axes[1, 0].get_xticklabels(), rotation=45)
    axes[1, 0].set_yscale('log')
    
    # Scatter plot: Followers vs Engagement
    axes[1, 1].scatter(df['followers'], df['engagement_rate'], alpha=0.5)
    axes[1, 1].set_title('Followers vs Engagement Rate')
    axes[1, 1].set_xlabel('Followers (log scale)')
    axes[1, 1].set_ylabel('Engagement Rate (%)')
    axes[1, 1].set_xscale('log')
    
    # Bar plot: Top pays
    top_countries = df['country'].value_counts().head(10)
    axes[1, 2].bar(range(len(top_countries)), top_countries.values)
    axes[1, 2].set_title('Top 10 Pays')
    axes[1, 2].set_xlabel('Pays')
    axes[1, 2].set_ylabel('Nombre d\'Influenceurs')
    axes[1, 2].set_xticks(range(len(top_countries)))
    axes[1, 2].set_xticklabels(top_countries.index, rotation=45)
    
    plt.tight_layout()
    plt.savefig('distributions.png', dpi=300, bbox_inches='tight')
    plt.show()

def clustering_analysis(df):
    """Analyse préliminaire pour clustering"""
    print("\n" + "="*60)
    print("🎯 ANALYSE POUR CLUSTERING (K-Means)")
    print("="*60)
    
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    
    # Sélection des features pour clustering
    features = ['followers', 'engagement_rate', 'posts', 'avg_likes', 'avg_comments']
    X = df[features].copy()
    
    # Scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Méthode du coude pour déterminer le nombre de clusters
    inertias = []
    K_range = range(2, 11)
    
    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)
    
    plt.figure(figsize=(10, 6))
    plt.plot(K_range, inertias, 'bo-')
    plt.xlabel('Nombre de Clusters')
    plt.ylabel('Inertie')
    plt.title('Méthode du Coude pour K-Means')
    plt.grid(True)
    plt.savefig('elbow_method.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Appliquer K-Means avec k=4 (exemple)
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    
    df['cluster'] = clusters
    
    print(f"\n📊 Distribution des clusters:")
    print(df['cluster'].value_counts().sort_index())
    
    print("\n📈 Caractéristiques moyennes par cluster:")
    cluster_stats = df.groupby('cluster')[features].mean()
    print(cluster_stats)
    
    return df

def outlier_detection(df):
    """Détection des outliers"""
    print("\n" + "="*60)
    print("⚠️ DÉTECTION DES OUTLIERS")
    print("="*60)
    
    from scipy import stats
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    outliers_info = {}
    for col in numeric_cols:
        if col != 'cluster':  # Exclure la colonne cluster si elle existe
            z_scores = np.abs(stats.zscore(df[col].dropna()))
            outliers = df[z_scores > 3][col]
            
            if len(outliers) > 0:
                outliers_info[col] = {
                    'count': len(outliers),
                    'percentage': (len(outliers) / len(df)) * 100,
                    'min': outliers.min(),
                    'max': outliers.max()
                }
    
    if outliers_info:
        print("Colonnes avec outliers (z-score > 3):")
        for col, info in outliers_info.items():
            print(f"  {col}: {info['count']} outliers ({info['percentage']:.1f}%)")
    else:
        print("✅ Aucun outlier détecté (z-score > 3)")

def export_analysis_results(df_eng):
    """Exporte les résultats de l'analyse"""
    print("\n" + "="*60)
    print("💾 EXPORT DES RÉSULTATS")
    print("="*60)
    
    # Export vers CSV
    df_eng.to_csv('influenceurs_enhanced.csv', index=False)
    print("✅ Données enrichies exportées: influenceurs_enhanced.csv")
    
    # Export vers PostgreSQL
    df_eng.to_sql('influenceurs_enhanced', engine, if_exists='replace', index=False)
    print("✅ Données enrichies importées dans PostgreSQL: table 'influenceurs_enhanced'")
    
    # Résumé statistique
    summary_stats = df_eng.describe().transpose()
    summary_stats.to_csv('summary_statistics.csv')
    print("✅ Statistiques exportées: summary_statistics.csv")

def main():
    """Fonction principale"""
    print("🔍 EXPLORATORY DATA ANALYSIS (EDA)")
    print("="*60)
    
    # 1. Chargement des données
    df = load_data()
    
    # 2. Statistiques basiques
    basic_statistics(df)
    
    # 3. Feature Engineering
    df_eng = feature_engineering(df)
    
    # 4. Analyse des corrélations
    correlation_analysis(df_eng)
    
    # 5. Visualisations
    visualize_distributions(df_eng)
    
    # 6. Analyse pour clustering
    df_clustered = clustering_analysis(df_eng)
    
    # 7. Détection des outliers
    outlier_detection(df_clustered)
    
    # 8. Export des résultats
    export_analysis_results(df_clustered)
    
    print("\n" + "="*60)
    print("🎉 ANALYSE TERMINÉE !")
    print("="*60)
    print("\n📁 FICHIERS CRÉÉS:")
    print("  - correlation_matrix.png")
    print("  - distributions.png")
    print("  - elbow_method.png")
    print("  - influenceurs_enhanced.csv")
    print("  - summary_statistics.csv")
    print("\n📊 TABLES POSTGRESQL:")
    print("  - influenceurs_simple (original)")
    print("  - influenceurs_enhanced (enrichie)")

if __name__ == "__main__":
    main()