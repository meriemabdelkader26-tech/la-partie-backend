# Guide de test et UI pour quotas & abonnements

## 1. Script de test rapide (Django shell)

Ouvrez le shell Django :

```bash
cd influBridge-back
python manage.py shell
```

Collez ce script pour simuler différents cas :

```python
from django.contrib.auth import get_user_model
from users.models import UserSubscription, SubscriptionPlan, SubscriptionStatus
from offer.models import Offer, OfferApplication
from django.utils import timezone

User = get_user_model()

# 1. Créer un utilisateur marque et influenceur
company = User.objects.create_user(email="marque@test.com", password="test", name="Marque Test", role="COMPANY")
influencer = User.objects.create_user(email="influ@test.com", password="test", name="Influ Test", role="INFLUENCER")

# 2. Vérifier le plan par défaut
print("Plan marque:", company.subscription.plan)
print("Plan influenceur:", influencer.subscription.plan)

# 3. Simuler 3 campagnes ce mois-ci (marque)
for i in range(3):
    Offer.objects.create(title=f"Campagne {i+1}", min_budget=100, max_budget=200, start_date=timezone.now().date(), end_date=timezone.now().date(), influencer_number=1, requirement="Test", objectif="Test", created_by=company)

# 4. Simuler 5 candidatures cette semaine (influenceur)
from offer.models import Offer
for i in range(5):
    offer = Offer.objects.create(title=f"Offre {i+1}", min_budget=100, max_budget=200, start_date=timezone.now().date(), end_date=timezone.now().date(), influencer_number=1, requirement="Test", objectif="Test", created_by=company)
    OfferApplication.objects.create(offer=offer, user=influencer, proposal="Test", asking_price=100)

# 5. Forcer un plan payant
company.subscription.plan = SubscriptionPlan.PLUS
company.subscription.status = SubscriptionStatus.ACTIVE
company.subscription.save()
print("Plan marque après upgrade:", company.subscription.plan)

# 6. Vérifier le quota restant
from users.billing import get_user_quota_snapshot
print(get_user_quota_snapshot(company))
print(get_user_quota_snapshot(influencer))
```

---

## 2. Guide UI (front)

### Marque (company)
- Allez sur `/company/campaigns/new`.
- Créez 3 campagnes → la 4e doit afficher un blocage + bouton "Upgrade".
- Cliquez sur "Upgrade to Plus" ou "Pro" → Stripe s’ouvre.
- Après paiement, retournez sur la page : quota débloqué.
- Gérez l’abonnement via "Manage billing" (portail Stripe).

### Influenceur
- Allez sur `/influencer/campaigns`.
- Postulez à 5 campagnes → la 6e doit afficher un blocage + bouton "Upgrade".
- Upgradez, puis vérifiez que la limite disparaît.

### Admin
- Vérifiez la table `user_subscriptions` dans l’admin Django pour voir les plans et statuts.

---

**Astuce** : Pour tester sans Stripe, mettez `STRIPE_SIMULATION_MODE=True` dans `.env`.
