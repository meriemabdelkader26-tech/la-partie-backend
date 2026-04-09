#!/usr/bin/env python
"""
Check which user is the admin
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

def check_admin():
    """Find the admin user"""
    
    print("=== Looking for ADMIN users ===\n")
    
    admins = User.objects.filter(role='ADMIN')
    
    for admin in admins:
        print(f"📧 Email: {admin.email}")
        print(f"   Name: {admin.name}")
        print(f"   ID: {admin.id}")
        print(f"   Role: {admin.role}")
        print(f"   Is Staff: {admin.is_staff}")
        print(f"   Is Superuser: {admin.is_superuser}")
        print("-" * 50)
    
    print("\n=== User ID 1 ===")
    try:
        user_1 = User.objects.get(pk=1)
        print(f"Email: {user_1.email}")
        print(f"Name: {user_1.name}")
        print(f"Role: {user_1.role}")
        
        if user_1.role == 'ADMIN':
            print("\n⚠️  USER ID 1 IS ADMIN!")
            print("The JWT token has userId: 1, which is the ADMIN user!")
            print("\nThe influencer user must have a different ID.")
    except User.DoesNotExist:
        print("User ID 1 not found")
    
    print("\n=== Looking for mahdilaith@gmail.com ===")
    try:
        influencer = User.objects.get(email='mahdilaith@gmail.com')
        print(f"Email: {influencer.email}")
        print(f"Name: {influencer.name}")
        print(f"ID: {influencer.id}")
        print(f"Role: {influencer.role}")
    except User.DoesNotExist:
        print("User not found")

if __name__ == '__main__':
    check_admin()
