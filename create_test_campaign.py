import os
import django
import random
from datetime import date, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from users.models import User, UserRole
from offer.models import Offer, OfferApplication, ApplicationStatus
from users.influencer_models import Influencer

def create_test_campaign_and_applications():
    email = "chahinebenali667@gmail.com"
    try:
        brand_user = User.objects.get(email=email)
        print(f"Found brand user: {brand_user.email}")
        
        # Ensure it's a company
        if brand_user.role != UserRole.COMPANY.value:
            print(f"Updating user role to COMPANY for {email}")
            brand_user.role = UserRole.COMPANY.value
            brand_user.save()
            
    except User.DoesNotExist:
        print(f"User {email} not found. Creating brand user...")
        brand_user = User.objects.create_user(
            email=email,
            password="password123",
            name="Chahine Brand",
            role=UserRole.COMPANY.value,
            email_verified=True,
            is_verify_by_admin=True,
            is_completed_profile=True
        )

    # Create a specific campaign for testing matching score
    # We'll create a campaign that fits some of our seeded influencers
    campaign_title = "Premium Coffee Brand Ambassador - Spring 2026"
    
    # Delete if exists to start fresh
    Offer.objects.filter(title=campaign_title, created_by=brand_user).delete()
    
    offer = Offer.objects.create(
        title=campaign_title,
        min_budget=400,
        max_budget=1200,
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=45),
        influencer_number=3,
        requirement="We are looking for lifestyle and food influencers to promote our new organic coffee blend. High-quality aesthetic photos and stories are required. Must have a warm, inviting content style.",
        objectif="Increase brand awareness among coffee enthusiasts and drive sales through a unique discount code.",
        created_by=brand_user
    )
    print(f"Created offer: {offer.title} (ID: {offer.id})")

    # Get some influencers to apply
    # We'll pick influencers with 'Food' or 'Lifestyle' interests if possible
    influencers = list(Influencer.objects.all())
    if not influencers:
        print("No influencers found! Please run seed_test_data.py first.")
        return

    # Select 5 random influencers to apply
    applicants = random.sample(influencers, min(5, len(influencers)))
    
    for inf in applicants:
        # Avoid duplicate applications
        OfferApplication.objects.filter(offer=offer, user=inf.user).delete()
        
        app = OfferApplication.objects.create(
            offer=offer,
            user=inf.user,
            proposal=f"Hi, I'm {inf.pseudo}. I love coffee and my audience is very engaged with lifestyle content. I'd love to collaborate!",
            asking_price=random.randint(450, 1100),
            status=ApplicationStatus.PENDING,
            cover_letter="I've been a coffee lover for years and frequently feature local cafes in my content. This partnership feels like a perfect fit for my brand aesthetic.",
            estimated_reach=random.randint(10000, 50000),
            delivery_days=random.randint(3, 10)
        )
        print(f"Influencer {inf.pseudo} (User: {inf.user.email}) applied to {offer.title}")

    print("\nCampaign and applications created successfully!")
    print(f"New Offer ID: {offer.id}")
    print(f"Number of applications: {offer.applications.count()}")

if __name__ == "__main__":
    create_test_campaign_and_applications()
