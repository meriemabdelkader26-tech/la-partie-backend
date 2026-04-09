"""
List all users and their roles
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("\n=== ALL USERS ===\n")

users = User.objects.all().order_by('role', 'name')

for user in users:
    status_icons = []
    if user.is_staff:
        status_icons.append("🔧 Staff")
    if user.is_superuser:
        status_icons.append("⭐ Superuser")
    if user.email_verified:
        status_icons.append("✓ Verified")
    if user.is_completed_profile:
        status_icons.append("✓ Profile")
    
    status = " | ".join(status_icons) if status_icons else "No special status"
    
    role_emoji = {
        'ADMIN': '👑',
        'INFLUENCER': '📸',
        'COMPANY': '🏢'
    }.get(user.role, '❓')
    
    print(f"{role_emoji} {user.role:12} | {user.name:25} | {user.email:40} | {status}")

print("\n" + "="*120)
print("\n💡 Tip: Your JWT token belongs to whichever user you logged in as.")
print("If you're getting ADMIN errors but want to test INFLUENCER features,")
print("you need to log in with an INFLUENCER account (like koreb69602@gamintor.com)")
