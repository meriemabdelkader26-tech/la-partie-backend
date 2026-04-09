"""
Check influencer data for specific user
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from users.influencer_models import Influencer, Image
from django.contrib.auth import get_user_model

User = get_user_model()

# Emma Laurent's user ID (from the global ID SW5mbHVlbmNlck5vZGU6OA== which decodes to Influencer ID 8)
try:
    influencer = Influencer.objects.get(pk=8)
    print("="*80)
    print(f"Influencer: {influencer.user.name} (ID: {influencer.id})")
    print("="*80)
    
    print(f"\n📸 Images (Generic Relation):")
    images = influencer.images.all()
    print(f"   Count: {images.count()}")
    for img in images:
        print(f"   - {img.url} (default: {img.is_default})")
    
    print(f"\n📱 Instagram Data:")
    print(f"   {influencer.instagram_data}")
    
    print(f"\n📷 Instagram Posts:")
    posts = influencer.instagram_posts.all()
    print(f"   Count: {posts.count()}")
    for post in posts[:3]:
        print(f"   - {post.post_name} ({post.likes} likes)")
    
    print(f"\n🎬 Instagram Reels:")
    reels = influencer.instagram_reels.all()
    print(f"   Count: {reels.count()}")
    for reel in reels[:3]:
        print(f"   - {reel.post_name} ({reel.views} views)")
    
    print("\n" + "="*80)
    
    # Check all images with content_type for this influencer
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Influencer)
    all_images = Image.objects.filter(content_type=ct, object_id=influencer.id)
    print(f"\n🔍 All Images (ContentType query):")
    print(f"   Count: {all_images.count()}")
    for img in all_images:
        print(f"   - {img.url}")
    
except Influencer.DoesNotExist:
    print("Influencer not found")
