"""
Fix corrupted disponibilite_collaboration enum values
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from users.influencer_models import Influencer
from django.db import transaction

print("="*80)
print("Fixing corrupted disponibilite_collaboration values")
print("="*80)

# Mapping of corrupted values to correct values
FIXES = {
    'EnumMeta.DISPONIBLE': 'disponible',
    'EnumMeta.OCCUPE': 'occupe',
    'EnumMeta.PARTIELLEMENT_DISPONIBLE': 'partiellement_disponible',
    'DISPONIBLE': 'disponible',
    'OCCUPE': 'occupe',
    'PARTIELLEMENT_DISPONIBLE': 'partiellement_disponible',
}

fixed_count = 0
error_count = 0

with transaction.atomic():
    for influencer in Influencer.objects.all():
        old_value = influencer.disponibilite_collaboration
        
        if old_value in FIXES:
            new_value = FIXES[old_value]
            influencer.disponibilite_collaboration = new_value
            influencer.save()
            fixed_count += 1
            print(f"✓ {influencer.user.name:30} | '{old_value}' → '{new_value}'")
        elif old_value in ['disponible', 'occupe', 'partiellement_disponible']:
            print(f"  {influencer.user.name:30} | Already correct: '{old_value}'")
        else:
            print(f"❌ {influencer.user.name:30} | Unknown value: '{old_value}'")
            error_count += 1

print("\n" + "="*80)
print(f"✅ Fixed {fixed_count} records")
if error_count > 0:
    print(f"❌ {error_count} records with unknown values")
print("="*80)

# Verify the fix
print("\n" + "="*80)
print("Verification - Current values:")
print("="*80)
from django.db.models import Count
counts = Influencer.objects.values('disponibilite_collaboration').annotate(count=Count('id'))
for item in counts:
    print(f"  {item['disponibilite_collaboration']}: {item['count']} influencers")
