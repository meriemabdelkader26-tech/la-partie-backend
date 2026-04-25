import os
import django
import random
from datetime import date, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from users.models import User, UserRole
from users.influencer_models import Influencer, ReseauSocial, OffreCollaboration
from users.company_models import Company, Address
from offer.models import Offer
from category.models import Category

def clear_data():
    print("Clearing existing test data (excluding superusers)...")
    # We only clear users with certain domains to avoid deleting real users if any
    test_users = User.objects.filter(email__endswith='@test.com')
    print(f"Deleting {test_users.count()} test users and related profiles...")
    test_users.delete()

def seed_categories():
    # Already have categories based on previous shell command, but ensuring some core ones
    categories = [
        'Fashion', 'Fitness & Health', 'Travel & Lifestyle', 
        'Food & Cooking', 'Technology & Gadgets', 'Gaming & Esports',
        'Beauty', 'Art & Photography'
    ]
    for cat_name in categories:
        Category.objects.get_or_create(name=cat_name)
    return list(Category.objects.all())

def create_influencers(categories, count=10):
    print(f"Creating {count} influencers...")
    influencers = []
    
    bios = [
        "Passionnée de mode et de photographie, je partage mon univers quotidien. ✨",
        "Traveler | Photographer | Life lover. Exploring the world one step at a time. 🌍",
        "Tech enthusiast and gadget reviewer. Always hunting for the latest innovations. 💻",
        "Fitness coach sharing workouts and healthy recipes. Let's get fit together! 💪",
        "Gamer and streamer. Joignez-vous à l'aventure sur Twitch! 🎮",
        "Foodie based in Paris. Discovering the best spots and hidden gems. 🍽️",
        "Artiste peintre et illustratrice. Je partage mon processus créatif. 🎨",
        "Lifestyle & Beauty blogger. Honest reviews and daily tips. 💄",
        "Expert en marketing digital et entrepreneuriat. Apprenez à booster votre business. 📈",
        "Maman blogueuse partageant ma vie de famille et mes astuces organisation. 👨‍👩‍👧‍👦"
    ]
    
    interests_pool = [
        "Mode", "Voyage", "Beauté", "Cuisine", "Sport", "Yoga", "Lecture", 
        "Cinéma", "Musique", "Technologie", "Photographie", "Art", "Gaming",
        "Décoration", "Jardinage", "Automobile", "Finance", "Entrepreneuriat"
    ]

    for i in range(count):
        email = f"influencer{i}@test.com"
        name = f"Influencer {i}"
        user = User.objects.create_user(
            email=email,
            password="password123",
            name=name,
            role=UserRole.INFLUENCER.value,
            email_verified=True,
            is_verify_by_admin=True,
            is_completed_profile=True
        )
        
        influencer = Influencer.objects.create(
            user=user,
            pseudo=f"influ_{random.randint(1000, 9999)}",
            biography=random.choice(bios),
            localisation=random.choice(["Paris", "Lyon", "Marseille", "Tunis", "Casablanca", "Brussels"]),
            centres_interet=random.sample(interests_pool, 3),
            type_contenu=["Photos", "Videos", "Stories"],
            disponibilite_collaboration='disponible'
        )
        
        # Add random categories
        influencer.selected_categories.add(*random.sample(categories, 2))
        
        # Add social networks
        platforms = ['Instagram', 'TikTok', 'YouTube']
        for platform in random.sample(platforms, 2):
            ReseauSocial.objects.create(
                influencer=influencer,
                plateforme=platform,
                url_profil=f"https://{platform.lower()}.com/user{i}",
                nombre_abonnes=random.randint(5000, 500000),
                taux_engagement=random.uniform(1.5, 8.5),
                moyenne_vues=random.randint(1000, 100000),
                moyenne_likes=random.randint(100, 10000),
                moyenne_commentaires=random.randint(10, 500)
            )
            
        # Add collaboration offers
        OffreCollaboration.objects.create(
            influencer=influencer,
            type_collaboration=random.choice(['post', 'story', 'reel', 'video']),
            tarif_minimum=random.randint(50, 500),
            tarif_maximum=random.randint(600, 2000),
            conditions="Flexible terms. Professional content delivery."
        )
        
        influencers.append(influencer)
        
    return influencers

def create_companies(count=5):
    print(f"Creating {count} companies...")
    companies = []
    
    domains = ['TECH', 'HLTH', 'RET', 'ENT', 'OTH']
    company_names = [
        "TechNova", "HealthFlow", "StyleVibe", "EcoSphere", "GameChanger",
        "TravelEase", "FoodLover", "ArtHub", "FitFirst", "GadgetWorld"
    ]
    
    for i in range(count):
        email = f"company{i}@test.com"
        name = random.choice(company_names) + f" {i}"
        user = User.objects.create_user(
            email=email,
            password="password123",
            name=name,
            role=UserRole.COMPANY.value,
            email_verified=True,
            is_verify_by_admin=True,
            is_completed_profile=True
        )
        
        address = Address.objects.create(
            address=f"{random.randint(1, 100)} Rue de Test",
            city="Paris",
            country="France"
        )
        
        company = Company.objects.create(
            user=user,
            company_name=name,
            description=f"Innovation leader in {name}. We value creative partnerships.",
            domain_activity=random.choice(domains),
            size=random.choice(['S', 'M', 'L', 'XL']),
            address=address,
            disponibilite_collaboration='disponible'
        )
        companies.append(company)
        
    return companies

def create_offers(companies, count=15):
    print(f"Creating {count} offers...")
    
    offer_templates = [
        {
            "title": "Summer Collection Launch",
            "requirement": "We need fashion influencers to showcase our new summer line. 1 Reel and 2 Stories required. Aesthetic: Minimalist and bright.",
            "objectif": "Brand awareness and drive traffic to our website.",
            "budget_min": 200, "budget_max": 800
        },
        {
            "title": "New Gadget Review",
            "requirement": "Looking for tech-savvy creators to do an unboxing and detailed review of our latest smartwatch. High quality video is a must.",
            "objectif": "Educate potential customers and generate sales.",
            "budget_min": 500, "budget_max": 1500
        },
        {
            "title": "Healthy Living Challenge",
            "requirement": "Join our 30-day fitness challenge! Post weekly updates using our organic supplements. Engaging captions required.",
            "objectif": "Community building and brand loyalty.",
            "budget_min": 300, "budget_max": 1000
        },
        {
            "title": "Travel Vlogger Partnership",
            "requirement": "Destination review for our new boutique hotel in Lyon. Full stay included plus stipend for content creation.",
            "objectif": "Increase bookings for the summer season.",
            "budget_min": 1000, "budget_max": 3000
        },
        {
            "title": "Gaming Tournament Promotion",
            "requirement": "Promote our upcoming Esports event. 1 Twitch shoutout and 2 Instagram posts. Passionate about gaming required.",
            "objectif": "Increase registrations for the tournament.",
            "budget_min": 400, "budget_max": 1200
        }
    ]

    for i in range(count):
        company = random.choice(companies)
        template = random.choice(offer_templates)
        
        Offer.objects.create(
            title=f"{template['title']} - Campaign {i}",
            min_budget=template['budget_min'],
            max_budget=template['budget_max'],
            start_date=date.today() + timedelta(days=random.randint(1, 10)),
            end_date=date.today() + timedelta(days=random.randint(30, 60)),
            influencer_number=random.randint(1, 5),
            requirement=template['requirement'],
            objectif=template['objectif'],
            created_by=company.user
        )

def run_seeding():
    print("Starting data seeding process...")
    clear_data()
    categories = seed_categories()
    create_influencers(categories, count=15)
    companies = create_companies(count=8)
    create_offers(companies, count=20)
    print("\nSeeding complete!")
    print(f"Total Users: {User.objects.count()}")
    print(f"Total Influencers: {Influencer.objects.count()}")
    print(f"Total Companies: {Company.objects.count()}")
    print(f"Total Offers: {Offer.objects.count()}")
    print("\nDon't forget to run the indexing script to update Qdrant!")

if __name__ == "__main__":
    run_seeding()
