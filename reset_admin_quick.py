#!/usr/bin/env python
"""
Quick script to reset superadmin password - Non-interactive version
Usage: python reset_admin_quick.py <email> <new_password>
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def reset_password(email, new_password):
    """Reset password for a specific user"""
    
    try:
        user = User.objects.get(email=email)
        
        if not user.is_superuser:
            print(f"❌ User {email} is not a superuser!")
            return False
        
        if len(new_password) < 8:
            print("❌ Password must be at least 8 characters long!")
            return False
        
        user.set_password(new_password)
        user.save()
        
        print(f"✅ Password successfully reset for {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Role: {user.role}")
        return True
        
    except User.DoesNotExist:
        print(f"❌ User with email {email} not found!")
        return False

def list_superusers():
    """List all superusers"""
    print("\n=== Available Superusers ===\n")
    superusers = User.objects.filter(is_superuser=True)
    
    if not superusers.exists():
        print("❌ No superusers found in the database!")
        return
    
    for user in superusers:
        print(f"Email: {user.email}")
        print(f"Name: {user.name}")
        print(f"Role: {user.role}")
        print("-" * 40)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # No arguments - list superusers
        list_superusers()
        print("\nUsage:")
        print("  python reset_admin_quick.py <email> <new_password>")
        print("\nExample:")
        print("  python reset_admin_quick.py admin@influBridge.com NewPassword123")
    elif len(sys.argv) == 3:
        # Reset password
        email = sys.argv[1]
        password = sys.argv[2]
        reset_password(email, password)
    else:
        print("❌ Invalid arguments!")
        print("\nUsage:")
        print("  python reset_admin_quick.py <email> <new_password>")
