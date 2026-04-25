from django.urls import path
from . import views
from . import proxy_views

urlpatterns = [
    # Health and Stats
    path('health/', views.HealthCheckView.as_view(), name='health-check'),
    path('stats/', views.StatsView.as_view(), name='stats'),
    path('categories/', views.CategoriesView.as_view(), name='categories'),
    path('countries/', views.CountriesView.as_view(), name='countries'),
    
    # Recommendations
    path('recommend/', views.RecommendView.as_view(), name='recommend'),
    path('recommend/offers/', views.PersonalizedOffersView.as_view(), name='personalized-offers-list'),
    path('recommend/offers/<int:influencer_id>/', views.PersonalizedOffersView.as_view(), name='personalized-offers'),
    path('recommend/influencers/<int:offer_id>/', views.OfferRecommendationsView.as_view(), name='offer-recommendations'),
    path('trending/', views.TrendingInfluencersView.as_view(), name='trending-influencers'),
    
    # Search
    path('search/', views.SearchView.as_view(), name='search'),
    
    # Influencer Detail
    path('influencer/<int:influencer_id>/', views.InfluencerDetailView.as_view(), name='influencer-detail'),

    # Profile Image Upload (REST fallback)
    path('upload-profile-image/', views.UploadProfileImageView.as_view(), name='upload-profile-image'),

    # Onboarding helpers
    path('selected-instagram-posts/', views.SelectedInstagramPostsView.as_view(), name='selected-instagram-posts'),
    path('profile-assets/', views.ProfileAssetsView.as_view(), name='profile-assets'),
    
    # Instagram Scraper
    path('instagram/scrape/', views.InstagramScraperView.as_view(), name='instagram-scrape'),
    
    # Generic Social Scraper
    # path('social/scrape/', views.SocialScraperView.as_view(), name='social-scrape'),
    
    # Proxy
    path('proxy/image/', proxy_views.proxy_image, name='proxy-image'),
    
    # AI
    path('generate-bio/', views.GenerateBioView.as_view(), name='generate-bio'),
    path('refine-conditions/', views.RefineOfferConditionsView.as_view(), name='refine-conditions'),
    
    # URL Checker
    path('check-url/', views.CheckUrlView.as_view(), name='check-url'),
    
    # Social Stats Fetcher
    path('fetch-social-stats/', views.FetchSocialStatsView.as_view(), name='fetch-social-stats'),
]
