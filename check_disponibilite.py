"""
Check disponibilite_collaboration values in database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from users.influencer_models import Influencer

print("="*80)
print("Checking disponibilite_collaboration values")
print("="*80)

influencers = Influencer.objects.all()

for inf in influencers:
    value = inf.disponibilite_collaboration
    print(f"{inf.user.name:30} | '{value}' | repr: {repr(value)} | bytes: {value.encode('utf-8')}")

print("\n" + "="*80)
print("Unique values:")
print("="*80)
unique_values = Influencer.objects.values_list('disponibilite_collaboration', flat=True).distinct()
for val in unique_values:
    print(f"  '{val}' -> repr: {repr(val)} -> bytes: {val.encode('utf-8')}")

print("\n" + "="*80)
print("Count by value:")
print("="*80)
from django.db.models import Count
counts = Influencer.objects.values('disponibilite_collaboration').annotate(count=Count('id'))
for item in counts:
    print(f"  {item['disponibilite_collaboration']}: {item['count']} influencers")
