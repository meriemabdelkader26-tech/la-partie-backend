# Subscription/Quota Migration Guide

## 1. Apply the new migration

```bash
python manage.py makemigrations users
python manage.py migrate users
```

Or, if you want to apply all migrations:

```bash
python manage.py migrate
```

## 2. Set Stripe price IDs and quotas in your environment

Add these to your `.env` or server environment (replace with your real Stripe price IDs):

```
STRIPE_PRICE_COMPANY_PLUS=price_xxx
STRIPE_PRICE_COMPANY_PRO=price_xxx
STRIPE_PRICE_INFLUENCER_PLUS=price_xxx
STRIPE_PRICE_INFLUENCER_PRO=price_xxx
COMPANY_FREE_CAMPAIGNS_PER_MONTH=3
COMPANY_PLUS_CAMPAIGNS_PER_MONTH=30
COMPANY_PRO_CAMPAIGNS_PER_MONTH=0
INFLUENCER_FREE_APPLICATIONS_PER_WEEK=5
INFLUENCER_PLUS_APPLICATIONS_PER_WEEK=40
INFLUENCER_PRO_APPLICATIONS_PER_WEEK=0
```

## 3. Test the flow

- Connect as a company and try to créer plus de 3 campagnes → blocage + bouton upgrade.
- Connect as an influencer and try to postuler à plus de 5 campagnes/semaine → blocage + bouton upgrade.
- Testez l’upgrade Stripe (checkout) et vérifiez l’activation automatique après paiement.
- Testez le portail Stripe (manage billing) pour annuler ou changer d’abonnement.
- Vérifiez que le quota se réinitialise chaque mois (marque) ou semaine (influenceur).

## 4. Debug

- Si un abonnement Stripe ne synchronise pas, vérifiez les logs du webhook `/api/payments/stripe/webhook/`.
- Pour forcer un plan, modifiez la table `user_subscriptions` dans l’admin Django.

---

**Astuce dev** : Pour simuler un paiement sans Stripe, mettez `STRIPE_SIMULATION_MODE=True` dans `.env`.
