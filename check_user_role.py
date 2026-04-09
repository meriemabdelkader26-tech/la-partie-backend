"""
Script to check user role for debugging
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

email = "daxag96250@gamintor.com"

try:
    user = User.objects.get(email=email)
    print(f"User found: {user.name} ({user.email})")
    print(f"Role: '{user.role}'")
    print(f"Role type: {type(user.role)}")
    print(f"Role repr: {repr(user.role)}")
    print(f"Is Influencer: {user.role == 'INFLUENCER'}")
    print(f"Is Active: {user.is_active}")
    print(f"Is Authenticated: {user.is_authenticated}")
    print(f"Email Verified: {user.email_verified}")
    print(f"Profile Completed: {user.is_completed_profile}")
    
    # Try to get influencer profile
    from users.influencer_models import Influencer
    try:
        influencer = Influencer.objects.get(user=user)
        print(f"\nInfluencer profile exists: {influencer}")
        print(f"Instagram Username: {influencer.instagram_username}")
    except Influencer.DoesNotExist:
        print("\nNo influencer profile found for this user")
        
except User.DoesNotExist:
    print(f"User with email {email} not found")
