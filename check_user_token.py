"""
Check user role and help debug token issues
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Check the user that should be an influencer
# email = input("Enter email to check: ").strip()

email ="koreb69602@gamintor.com"

try:
    user = User.objects.get(email=email)
    print(f"\n=== User Details ===")
    print(f"Name: {user.name}")
    print(f"Email: {user.email}")
    print(f"Role: {user.role}")
    print(f"Role type: {type(user.role)}")
    print(f"Is Active: {user.is_active}")
    print(f"Is Staff: {user.is_staff}")
    print(f"Email Verified: {user.email_verified}")
    print(f"Profile Completed: {user.is_completed_profile}")
    
    # Check if influencer profile exists
    from users.influencer_models import Influencer
    try:
        influencer = Influencer.objects.get(user=user)
        print(f"\n=== Influencer Profile ===")
        print(f"Pseudo: {influencer.pseudo}")
        print(f"Instagram: {influencer.instagram_username}")
        print(f"Location: {influencer.localisation}")
    except Influencer.DoesNotExist:
        print("\n❌ No influencer profile found")
    
    # Provide guidance
    print("\n=== Action Required ===")
    if user.role != 'INFLUENCER':
        print(f"⚠️  User role is '{user.role}', not 'INFLUENCER'")
        print("You need to:")
        print("1. Log out from your current session")
        print("2. Log in again to get a fresh token")
        print("3. Or use an account with INFLUENCER role")
    else:
        print("✓ User role is INFLUENCER")
        print("If you're still getting ADMIN error, log out and log in again to refresh your token")
        
except User.DoesNotExist:
    print(f"❌ User with email '{email}' not found")
