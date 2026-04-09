#!/usr/bin/env python
"""
List all users and their roles
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

def list_users():
    """List all users and their roles"""
    
    print("=== All Users in Database ===\n")
    
    users = User.objects.all()
    
    for user in users:
        print(f"📧 Email: {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Role: {user.role}")
        print(f"   Is Active: {user.is_active}")
        print(f"   Is Staff: {user.is_staff}")
        print(f"   Is Superuser: {user.is_superuser}")
        print(f"   Profile Completed: {user.is_completed_profile}")
        print("-" * 50)

if __name__ == '__main__':
    list_users()
