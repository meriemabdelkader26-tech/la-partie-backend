#!/usr/bin/env python
"""
Script to reset superadmin password
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

def reset_superadmin_password():
    """Reset password for superadmin"""
    
    print("\n=== Reset Superadmin Password ===\n")
    
    # List all superusers
    superusers = User.objects.filter(is_superuser=True)
    
    if not superusers.exists():
        print("❌ No superusers found in the database!")
        return
    
    print("Available superusers:")
    for i, user in enumerate(superusers, 1):
        print(f"{i}. Email: {user.email} | Name: {user.name}")
    
    # Select user
    if superusers.count() == 1:
        user = superusers.first()
        print(f"\n✓ Automatically selected: {user.email}")
    else:
        try:
            choice = int(input("\nSelect user number: "))
            user = list(superusers)[choice - 1]
        except (ValueError, IndexError):
            print("❌ Invalid selection!")
            return
    
    # Get new password
    print(f"\nResetting password for: {user.email}")
    new_password = input("Enter new password: ")
    confirm_password = input("Confirm new password: ")
    
    if new_password != confirm_password:
        print("❌ Passwords don't match!")
        return
    
    if len(new_password) < 8:
        print("❌ Password must be at least 8 characters long!")
        return
    
    # Set new password
    user.set_password(new_password)
    user.save()
    
    print(f"\n✅ Password successfully reset for {user.email}")
    print(f"   Name: {user.name}")
    print(f"   Role: {user.role}")

if __name__ == '__main__':
    try:
        reset_superadmin_password()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
