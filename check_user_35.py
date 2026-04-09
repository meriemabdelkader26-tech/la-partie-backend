"""
Check specific user by ID
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

user_id = 35  # From the JWT token

try:
    user = User.objects.get(pk=user_id)
    print(f"\n=== User ID {user_id} Details ===")
    print(f"Name: {user.name}")
    print(f"Email: {user.email}")
    print(f"Role: '{user.role}'")
    print(f"Role type: {type(user.role)}")
    print(f"Role repr: {repr(user.role)}")
    print(f"Is Active: {user.is_active}")
    print(f"Is Staff: {user.is_staff}")
    print(f"Email Verified: {user.email_verified}")
    print(f"Profile Completed: {user.is_completed_profile}")
    
    print("\n=== ISSUE IDENTIFIED ===")
    if user.role != 'INFLUENCER':
        print(f"❌ User role in DATABASE is '{user.role}'")
        print(f"✓ User role in JWT TOKEN is 'INFLUENCER'")
        print("\nThe role was changed AFTER the token was generated!")
        print("The token has the OLD role, but the database has been updated.")
        print("\nSOLUTION: Log out and log in again to get a fresh token.")
    else:
        print("✓ User role in database matches token (INFLUENCER)")
        print("This shouldn't be happening... checking further...")
        
except User.DoesNotExist:
    print(f"❌ User with ID {user_id} not found")
