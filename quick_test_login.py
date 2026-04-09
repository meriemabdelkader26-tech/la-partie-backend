#!/usr/bin/env python
"""
Quick test of admin login with specific credentials
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

User = get_user_model()

def quick_test():
    """Quick test with hardcoded credentials"""
    
    email = 'admin@influBridge.com'
    password = 'Admin123456'  # The password we just set
    
    print("\n=== Quick Admin Login Test ===\n")
    print(f"Testing: {email}")
    
    # Test authentication
    user = authenticate(username=email, password=password)
    
    if user is not None:
        print("\n✅ AUTHENTICATION SUCCESSFUL!")
        print(f"\nUser can {'✅ ACCESS' if user.is_staff else '❌ NOT ACCESS'} Django admin")
        print(f"\n🌐 Admin URL: http://127.0.0.1:8000/admin/")
        print(f"📧 Email: {email}")
        print(f"🔑 Password: {password}")
        
        print(f"\nStatus:")
        print(f"  is_active: {user.is_active}")
        print(f"  is_staff: {user.is_staff}")
        print(f"  is_superuser: {user.is_superuser}")
        
        if not user.is_staff:
            print("\n⚠️  Fixing is_staff...")
            user.is_staff = True
            user.save()
            print("✅ Fixed!")
            
    else:
        print("\n❌ AUTHENTICATION FAILED!")
        print("\nTrying to find user...")
        
        try:
            user = User.objects.get(email=email)
            print(f"✅ User exists")
            print(f"   is_active: {user.is_active}")
            print(f"   is_staff: {user.is_staff}")
            print("\n❌ Password is incorrect!")
            print("\nReset password with:")
            print(f"   python reset_admin_quick.py {email} NewPassword123")
        except User.DoesNotExist:
            print(f"❌ User {email} not found")

if __name__ == '__main__':
    try:
        quick_test()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
