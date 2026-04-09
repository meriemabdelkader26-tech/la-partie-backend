"""
Fix corrupted enum values in the database
Converts 'EnumMeta.INFLUENCER' -> 'INFLUENCER', etc.
Also fixes other corrupted enum values in Influencer and ReseauSocial models
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from users.influencer_models import Influencer, ReseauSocial

User = get_user_model()


def normalize_enum_value(value):
    """Extract clean enum value from corrupted string"""
    if not value:
        return value
    # Convert 'EnumMeta.DISPONIBLE' -> 'DISPONIBLE'
    if isinstance(value, str) and '.' in value:
        return value.split('.')[-1]
    return value


def fix_corrupted_roles():
    """Fix all users with corrupted role values"""
    
    print("=" * 60)
    print("FIXING USER ROLES")
    print("=" * 60)
    
    corrupted_users = User.objects.filter(role__contains='EnumMeta.')
    
    print(f"Found {corrupted_users.count()} users with corrupted roles")
    
    if corrupted_users.count() == 0:
        print("✓ No corrupted roles found!")
    else:
        fixed_count = 0
        
        with transaction.atomic():
            for user in corrupted_users:
                old_role = user.role
                new_role = normalize_enum_value(old_role)
                
                user.role = new_role
                user.save(update_fields=['role'])
                
                print(f"  Fixed user {user.email}: '{old_role}' -> '{new_role}'")
                fixed_count += 1
        
        print(f"\n✓ Successfully fixed {fixed_count} user roles!")


def fix_corrupted_influencer_disponibilite():
    """Fix corrupted disponibilite_collaboration values"""
    
    print("\n" + "=" * 60)
    print("FIXING INFLUENCER DISPONIBILITE")
    print("=" * 60)
    
    corrupted_influencers = Influencer.objects.filter(disponibilite_collaboration__contains='EnumMeta.')
    
    print(f"Found {corrupted_influencers.count()} influencers with corrupted disponibilite")
    
    if corrupted_influencers.count() == 0:
        print("✓ No corrupted disponibilite values found!")
    else:
        fixed_count = 0
        
        # Map from GraphQL enum to database choices
        mapping = {
            'DISPONIBLE': 'disponible',
            'OCCUPE': 'occupe',
            'PARTIELLEMENT_DISPONIBLE': 'partiellement_disponible',
        }
        
        with transaction.atomic():
            for influencer in corrupted_influencers:
                old_value = influencer.disponibilite_collaboration
                clean_value = normalize_enum_value(old_value)
                new_value = mapping.get(clean_value, clean_value.lower())
                
                influencer.disponibilite_collaboration = new_value
                influencer.save(update_fields=['disponibilite_collaboration'])
                
                print(f"  Fixed {influencer.user.email}: '{old_value}' -> '{new_value}'")
                fixed_count += 1
        
        print(f"\n✓ Successfully fixed {fixed_count} influencer disponibilite values!")


def fix_corrupted_reseau_social():
    """Fix corrupted plateforme and frequence_publication values"""
    
    print("\n" + "=" * 60)
    print("FIXING RESEAUX SOCIAUX")
    print("=" * 60)
    
    # Fix plateforme
    corrupted_plateformes = ReseauSocial.objects.filter(plateforme__contains='EnumMeta.')
    print(f"Found {corrupted_plateformes.count()} reseaux_sociaux with corrupted plateforme")
    
    if corrupted_plateformes.count() > 0:
        fixed_count = 0
        
        with transaction.atomic():
            for reseau in corrupted_plateformes:
                old_value = reseau.plateforme
                new_value = normalize_enum_value(old_value)
                # Capitalize first letter to match database choices
                new_value = new_value.capitalize() if new_value else new_value
                
                reseau.plateforme = new_value
                reseau.save(update_fields=['plateforme'])
                
                print(f"  Fixed plateforme for {reseau.influencer.user.email}: '{old_value}' -> '{new_value}'")
                fixed_count += 1
        
        print(f"\n✓ Successfully fixed {fixed_count} plateforme values!")
    else:
        print("✓ No corrupted plateforme values found!")
    
    # Fix frequence_publication
    corrupted_frequences = ReseauSocial.objects.filter(frequence_publication__contains='EnumMeta.')
    print(f"\nFound {corrupted_frequences.count()} reseaux_sociaux with corrupted frequence_publication")
    
    if corrupted_frequences.count() > 0:
        fixed_count = 0
        
        # Map from GraphQL enum to database choices
        mapping = {
            'QUOTIDIENNE': 'quotidienne',
            'HEBDOMADAIRE': 'hebdomadaire',
            'BI_HEBDOMADAIRE': 'bi_hebdomadaire',
            'MENSUELLE': 'mensuelle',
        }
        
        with transaction.atomic():
            for reseau in corrupted_frequences:
                old_value = reseau.frequence_publication
                clean_value = normalize_enum_value(old_value)
                new_value = mapping.get(clean_value, clean_value.lower())
                
                reseau.frequence_publication = new_value
                reseau.save(update_fields=['frequence_publication'])
                
                print(f"  Fixed frequence for {reseau.influencer.user.email}: '{old_value}' -> '{new_value}'")
                fixed_count += 1
        
        print(f"\n✓ Successfully fixed {fixed_count} frequence_publication values!")
    else:
        print("✓ No corrupted frequence_publication values found!")


def verify_all_fixes():
    """Verify that all corruptions have been fixed"""
    
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    issues = []
    
    # Check users
    corrupted_users = User.objects.filter(role__contains='EnumMeta.')
    if corrupted_users.count() > 0:
        issues.append(f"⚠ {corrupted_users.count()} users still have corrupted roles")
    else:
        print("✓ All user roles are clean")
    
    # Check influencer disponibilite
    corrupted_disponibilite = Influencer.objects.filter(disponibilite_collaboration__contains='EnumMeta.')
    if corrupted_disponibilite.count() > 0:
        issues.append(f"⚠ {corrupted_disponibilite.count()} influencers still have corrupted disponibilite")
    else:
        print("✓ All influencer disponibilite values are clean")
    
    # Check reseau social plateforme
    corrupted_plateforme = ReseauSocial.objects.filter(plateforme__contains='EnumMeta.')
    if corrupted_plateforme.count() > 0:
        issues.append(f"⚠ {corrupted_plateforme.count()} reseaux_sociaux still have corrupted plateforme")
    else:
        print("✓ All reseau social plateforme values are clean")
    
    # Check reseau social frequence
    corrupted_frequence = ReseauSocial.objects.filter(frequence_publication__contains='EnumMeta.')
    if corrupted_frequence.count() > 0:
        issues.append(f"⚠ {corrupted_frequence.count()} reseaux_sociaux still have corrupted frequence_publication")
    else:
        print("✓ All reseau social frequence_publication values are clean")
    
    print("\n" + "=" * 60)
    if issues:
        print("❌ ISSUES FOUND:")
        for issue in issues:
            print(issue)
    else:
        print("✅ ALL ENUM VALUES ARE CLEAN!")
    print("=" * 60)


if __name__ == '__main__':
    print("\n🔧 Starting Database Cleanup...\n")
    
    fix_corrupted_roles()
    fix_corrupted_influencer_disponibilite()
    fix_corrupted_reseau_social()
    verify_all_fixes()
    
    print("\n✅ Database cleanup completed!\n")
