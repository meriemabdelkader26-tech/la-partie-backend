"""
Generate a fresh JWT token for login
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import get_user_model
import graphene
from graphql_jwt.shortcuts import get_token

User = get_user_model()

# The influencer account
email = "daxag96250@gamintor.com"
password = input(f"Enter password for {email}: ").strip()

try:
    user = User.objects.get(email=email)
    
    # Check password
    if not user.check_password(password):
        print("❌ Invalid password!")
        exit(1)
    
    # Generate fresh token
    token = get_token(user)
    
    print("\n" + "="*80)
    print("✅ SUCCESS! Fresh token generated")
    print("="*80)
    print(f"\nUser: {user.name}")
    print(f"Email: {user.email}")
    print(f"Role: {user.role}")
    print(f"\n🔑 JWT Token:")
    print(token)
    print("\n" + "="*80)
    print("\n📋 Copy this token and use it in your GraphQL requests:")
    print('Authorization: Bearer ' + token)
    print("\n" + "="*80)
    
except User.DoesNotExist:
    print(f"❌ User with email '{email}' not found")
