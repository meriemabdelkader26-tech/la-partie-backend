#!/usr/bin/env python
"""
Script to check admin user status and fix permissions
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

def check_admin_status():
    """Check admin user status and permissions"""
    
    print("\n=== Admin Status Check ===\n")
    
    try:
        admin = User.objects.get(email='admin@influBridge.com')
        
        print(f"Email: {admin.email}")
        print(f"Name: {admin.name}")
        print(f"Role: {admin.role}")
        print(f"\nPermissions:")
        print(f"  ✓ is_active: {admin.is_active}")
        print(f"  ✓ is_staff: {admin.is_staff}")
        print(f"  ✓ is_superuser: {admin.is_superuser}")
        print(f"  ✓ email_verified: {admin.email_verified}")
        print(f"  ✓ is_verify_by_admin: {admin.is_verify_by_admin}")
        print(f"  ✓ is_banned: {admin.is_banned}")
        
        # Check if admin can access Django admin
        if not admin.is_staff:
            print("\n❌ PROBLEM: is_staff is False")
            print("   Admin cannot access Django admin panel without is_staff=True")
            fix = input("\nFix this issue? (y/n): ")
            if fix.lower() == 'y':
                admin.is_staff = True
                admin.save()
                print("✅ Fixed: is_staff set to True")
        
        if not admin.is_superuser:
            print("\n⚠️  WARNING: is_superuser is False")
            print("   Admin will have limited permissions")
            fix = input("\nMake this user a superuser? (y/n): ")
            if fix.lower() == 'y':
                admin.is_superuser = True
                admin.save()
                print("✅ Fixed: is_superuser set to True")
        
        if not admin.is_active:
            print("\n❌ PROBLEM: is_active is False")
            print("   Admin account is disabled")
            fix = input("\nActivate this account? (y/n): ")
            if fix.lower() == 'y':
                admin.is_active = True
                admin.save()
                print("✅ Fixed: is_active set to True")
        
        if admin.is_banned:
            print("\n❌ PROBLEM: is_banned is True")
            print("   Admin account is banned")
            fix = input("\nUnban this account? (y/n): ")
            if fix.lower() == 'y':
                admin.is_banned = False
                admin.save()
                print("✅ Fixed: is_banned set to False")
        
        # Reload and show final status
        admin.refresh_from_db()
        
        print("\n" + "="*50)
        print("FINAL STATUS:")
        print("="*50)
        
        can_login = admin.is_active and admin.is_staff
        
        if can_login:
            print("✅ Admin can now access Django admin panel!")
            print(f"\n🌐 Admin URL: http://127.0.0.1:8000/admin/")
            print(f"📧 Email: {admin.email}")
            print("🔑 Password: [The one you just set]")
        else:
            print("❌ Admin still cannot access Django admin panel")
            print("\nRequired for Django admin access:")
            print(f"  - is_active: {admin.is_active} {'✅' if admin.is_active else '❌'}")
            print(f"  - is_staff: {admin.is_staff} {'✅' if admin.is_staff else '❌'}")
        
    except User.DoesNotExist:
        print("❌ Admin user (admin@influBridge.com) not found!")
        print("\nCreate a new superuser:")
        print("  python manage.py createsuperuser")

if __name__ == '__main__':
    try:
        check_admin_status()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
