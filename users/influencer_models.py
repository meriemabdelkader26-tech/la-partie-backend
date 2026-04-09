from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from category.models import Category

User = get_user_model()


class Image(models.Model):
    """Generic Image model that can be related to any model (Influencer, Company, etc.)"""
    
    url = models.URLField(max_length=1000)  # Increased for long URLs (e.g., Cloudinary, Instagram CDN)
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    
    # Generic foreign key to allow relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'images'
        verbose_name = 'Image'
        verbose_name_plural = 'Images'
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        default_text = " (Default)" if self.is_default else ""
        return f"Image for {self.content_object}{default_text}"
    
    def save(self, *args, **kwargs):
        # If this image is set as default, remove default from other images for the same object
        if self.is_default:
            Image.objects.filter(
                content_type=self.content_type,
                object_id=self.object_id,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Influencer(models.Model):
    """Influencer profile extending User model"""
    
    DISPONIBILITE_CHOICES = [
        ('disponible', 'Disponible'),
        ('occupe', 'Occupé'),
        ('partiellement_disponible', 'Partiellement disponible'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='influencer_profile')
    
    # Basic Information
    instagram_username = models.CharField(max_length=255, blank=True, null=True)
    pseudo = models.CharField(max_length=255, blank=True, null=True)
    biography = models.TextField(blank=True, null=True)
    site_web = models.URLField(blank=True, null=True)
    localisation = models.CharField(max_length=255, blank=True, null=True)
    
    # Instagram API Data (stored as JSON)
    instagram_data = models.JSONField(default=dict, blank=True, null=True)
    
    # Categories and Interests
    selected_categories = models.ManyToManyField(
        Category, 
        related_name='influencers_categories',
        blank=True
    )
    
    # Additional fields stored as JSON for flexibility
    langues = models.JSONField(default=list, blank=True)  # ["Français", "Anglais", "Arabe"]
    centres_interet = models.JSONField(default=list, blank=True)  # ["Mode", "Voyage", "Beauté"]
    type_contenu = models.JSONField(default=list, blank=True)  # ["Photo", "Vidéo", "Story"]
    
    # Collaboration
    disponibilite_collaboration = models.CharField(
        max_length=50,
        choices=DISPONIBILITE_CHOICES,
        default='disponible'
    )
    
    # Generic relation to images
    images = GenericRelation(Image, related_query_name='influencer')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'influencers'
        verbose_name = 'Influencer'
        verbose_name_plural = 'Influencers'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.name} - {self.pseudo or 'No pseudo'}"

    def _extract_instagram_numeric(self, keys, default=0.0):
        """Best-effort parser for numeric values stored in instagram_data."""
        data = self.instagram_data or {}
        if not isinstance(data, dict):
            return default

        for key in keys:
            raw_value = data.get(key)
            if raw_value is None:
                continue

            if isinstance(raw_value, dict):
                if "count" in raw_value:
                    raw_value = raw_value.get("count")
                elif "value" in raw_value:
                    raw_value = raw_value.get("value")
                else:
                    continue

            if isinstance(raw_value, (int, float)):
                return float(raw_value)

            text = str(raw_value).replace(',', '').replace('%', '').strip()
            try:
                return float(text)
            except (TypeError, ValueError):
                continue

        return default
    
    @property
    def followers_totaux(self):
        """Calculate total followers across all platforms"""
        social_total = sum(rs.nombre_abonnes for rs in self.reseaux_sociaux.all())
        if social_total > 0:
            return social_total

        # Fallback to imported Instagram profile data when social networks are not saved yet.
        fallback = self._extract_instagram_numeric(
            [
                'followers',
                'follower_count',
                'followers_count',
                'edge_followed_by',
                'nombre_abonnes',
            ],
            default=0.0,
        )
        if fallback > 0:
            return int(fallback)

        # Final fallback for legacy profiles: infer a rough audience size from content views.
        reels = list(self.instagram_reels.all())
        total_views = sum((reel.views or 0) for reel in reels)
        if total_views > 0 and len(reels) > 0:
            avg_views = total_views / len(reels)
            return int(avg_views)

        return 0
    
    @property
    def engagement_moyen_global(self):
        """Calculate average engagement across all platforms"""
        reseaux = self.reseaux_sociaux.all()
        if reseaux:
            return sum(rs.taux_engagement for rs in reseaux) / len(reseaux)

        direct_engagement = self._extract_instagram_numeric(
            [
                'engagement_rate',
                'taux_engagement',
                'engagement',
            ],
            default=0.0,
        )
        if direct_engagement > 0:
            return direct_engagement

        followers = max(self.followers_totaux, 0)
        posts = list(self.instagram_posts.all())
        reels = list(self.instagram_reels.all())
        total_content = len(posts) + len(reels)
        if total_content == 0:
            return 0.0

        total_interactions = 0
        for post in posts:
            total_interactions += (post.likes or 0) + (post.comments or 0)
        for reel in reels:
            total_interactions += (reel.likes or 0) + (reel.comments or 0)

        avg_interactions_per_content = total_interactions / total_content
        if followers > 0:
            return (avg_interactions_per_content / followers) * 100

        # Last fallback when followers are missing: use reel views as denominator.
        total_views = sum((reel.views or 0) for reel in reels)
        if total_views > 0:
            return (total_interactions / total_views) * 100

        return 0.0
    
    def calculate_croissance_mensuelle(self):
        """Calculate monthly growth from historical snapshots when available."""
        snapshots = self.statistiques_historique.order_by('-mois')[:2]
        if len(snapshots) < 2:
            return 0.0

        current_followers = snapshots[0].followers_totaux or 0
        previous_followers = snapshots[1].followers_totaux or 0

        if previous_followers <= 0:
            return 0.0

        return ((current_followers - previous_followers) / previous_followers) * 100


class ReseauSocial(models.Model):
    """Social network profile for influencer"""
    
    PLATEFORME_CHOICES = [
        ('Instagram', 'Instagram'),
        ('TikTok', 'TikTok'),
        ('YouTube', 'YouTube'),
        ('Facebook', 'Facebook'),
        ('Twitter', 'Twitter'),
        ('LinkedIn', 'LinkedIn'),
        ('Snapchat', 'Snapchat'),
    ]
    
    FREQUENCE_CHOICES = [
        ('quotidienne', 'Quotidienne'),
        ('hebdomadaire', 'Hebdomadaire'),
        ('bi_hebdomadaire', 'Bi-hebdomadaire'),
        ('mensuelle', 'Mensuelle'),
    ]
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='reseaux_sociaux'
    )
    
    plateforme = models.CharField(max_length=50, choices=PLATEFORME_CHOICES)
    url_profil = models.URLField(max_length=500)  # Increased for long Instagram URLs
    nombre_abonnes = models.IntegerField(default=0)
    taux_engagement = models.FloatField(default=0.0)  # Percentage
    moyenne_vues = models.IntegerField(default=0)
    moyenne_likes = models.IntegerField(default=0)
    moyenne_commentaires = models.IntegerField(default=0)
    frequence_publication = models.CharField(
        max_length=50,
        choices=FREQUENCE_CHOICES,
        default='hebdomadaire'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reseaux_sociaux'
        verbose_name = 'Réseau Social'
        verbose_name_plural = 'Réseaux Sociaux'
        ordering = ['-nombre_abonnes']
        unique_together = ['influencer', 'plateforme']
    
    def __str__(self):
        return f"{self.influencer.user.name} - {self.plateforme}"


class InfluencerWork(models.Model):
    """Previous work/collaboration for influencer"""
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='previous_works'
    )
    
    brand_name = models.CharField(max_length=255)  # nom_marque
    campaign = models.CharField(max_length=255)  # campagne
    period = models.CharField(max_length=100)  # periode
    results = models.TextField(blank=True, null=True)  # resultats
    publication_link = models.URLField(max_length=1000, blank=True, null=True)  # lien_publication
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'influencer_works'
        verbose_name = 'Influencer Work'
        verbose_name_plural = 'Influencer Works'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.influencer.user.name} - {self.brand_name}"


class InstagramReel(models.Model):
    """Instagram Reel data for influencer portfolio"""
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='instagram_reels'
    )
    
    # Instagram data
    instagram_id = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=255)
    video_url = models.URLField(max_length=2000)  # Instagram CDN URLs can be very long
    thumbnail_url = models.URLField(max_length=2000)
    post_name = models.CharField(max_length=500)
    duration = models.IntegerField()  # in seconds
    taken_at = models.DateTimeField()
    
    # Engagement metrics
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    views = models.IntegerField(default=0)
    
    # Metadata
    username = models.CharField(max_length=255)
    hashtags = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'instagram_reels'
        verbose_name = 'Instagram Reel'
        verbose_name_plural = 'Instagram Reels'
        ordering = ['-taken_at']
    
    def __str__(self):
        return f"{self.username} - {self.post_name[:50]}"


class InstagramPost(models.Model):
    """Instagram Post data for influencer portfolio"""
    
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('carousel', 'Carousel'),
        ('video', 'Video'),
    ]
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='instagram_posts'
    )
    
    # Instagram data
    instagram_id = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=255)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    image_url = models.URLField(max_length=2000)  # Instagram CDN URLs can be very long
    thumbnail_url = models.URLField(max_length=2000)
    post_name = models.CharField(max_length=500)
    taken_at = models.DateTimeField()
    
    # Engagement metrics
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    
    # Metadata
    username = models.CharField(max_length=255)
    carousel_media = models.JSONField(default=list, blank=True)  # For carousel posts
    hashtags = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'instagram_posts'
        verbose_name = 'Instagram Post'
        verbose_name_plural = 'Instagram Posts'
        ordering = ['-taken_at']
    
    def __str__(self):
        return f"{self.username} - {self.post_name[:50]}"


class InfluencerImage(models.Model):
    """DEPRECATED: Use Image model instead. Kept for backward compatibility."""
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='old_images'
    )
    
    url = models.URLField(max_length=1000)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'influencer_images'
        verbose_name = 'Influencer Image (Deprecated)'
        verbose_name_plural = 'Influencer Images (Deprecated)'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        default_text = " (Default)" if self.is_default else ""
        return f"{self.influencer.user.name} - Image{default_text}"


class PortfolioMedia(models.Model):
    """Portfolio media items for influencer"""
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='portfolio_media'
    )
    
    image_url = models.URLField(max_length=1000)
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date_creation = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'portfolio_media'
        verbose_name = 'Portfolio Media'
        verbose_name_plural = 'Portfolio Media'
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.influencer.user.name} - {self.titre}"


class OffreCollaboration(models.Model):
    """Collaboration offer pricing and conditions"""
    
    TYPE_CHOICES = [
        ('placement_produit', 'Placement produit'),
        ('story', 'Story'),
        ('post', 'Post'),
        ('video', 'Vidéo'),
        ('reel', 'Reel'),
        ('live', 'Live'),
        ('ambassadeur', 'Ambassadeur'),
    ]
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='offres_collaboration'
    )
    
    type_collaboration = models.CharField(max_length=100, choices=TYPE_CHOICES)
    tarif_minimum = models.DecimalField(max_digits=10, decimal_places=2)
    tarif_maximum = models.DecimalField(max_digits=10, decimal_places=2)
    conditions = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'offres_collaboration'
        verbose_name = 'Offre de Collaboration'
        verbose_name_plural = 'Offres de Collaboration'
        ordering = ['type_collaboration']
    
    def __str__(self):
        return f"{self.influencer.user.name} - {self.type_collaboration}"


class StatistiquesGlobales(models.Model):
    """Global statistics for influencer (historical tracking)"""
    
    influencer = models.ForeignKey(
        Influencer,
        on_delete=models.CASCADE,
        related_name='statistiques_historique'
    )
    
    followers_totaux = models.IntegerField(default=0)
    engagement_moyen_global = models.FloatField(default=0.0)
    croissance_mensuelle = models.FloatField(default=0.0)  # Percentage
    
    # Month tracking
    mois = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'statistiques_globales'
        verbose_name = 'Statistiques Globales'
        verbose_name_plural = 'Statistiques Globales'
        ordering = ['-mois']
        unique_together = ['influencer', 'mois']
    
    def __str__(self):
        return f"{self.influencer.user.name} - {self.mois.strftime('%B %Y')}"
