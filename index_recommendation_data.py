import os
import django
import json
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'influBridge.settings')
django.setup()

from users.influencer_models import Influencer
from offer.models import Offer

# Credentials (using same as index_rag_data.py)
QDRANT_URL = "https://73b0fb86-a6a8-45eb-8e70-cc1697987b8a.eu-central-1-0.aws.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MTU5NTBjZDMtNTUxNy00Y2Q0LTlmNDMtZjgzNzBlNDhkY2ZiIn0.n1xPzYsMFfvbcjFVJdjPuNENFLLjM5tET0-Yr7n9RTw"

INFLUENCER_COLLECTION = "influencer_profiles"
OFFER_COLLECTION = "offer_requirements"

def setup_collections(client):
    collections = client.get_collections().collections
    
    # Setup Influencer Collection
    exists = any(c.name == INFLUENCER_COLLECTION for c in collections)
    if exists:
        print(f"Collection {INFLUENCER_COLLECTION} exists. Recreating...")
        client.delete_collection(collection_name=INFLUENCER_COLLECTION)
    
    client.create_collection(
        collection_name=INFLUENCER_COLLECTION,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    )
    
    # Setup Offer Collection
    exists = any(c.name == OFFER_COLLECTION for c in collections)
    if exists:
        print(f"Collection {OFFER_COLLECTION} exists. Recreating...")
        client.delete_collection(collection_name=OFFER_COLLECTION)
        
    client.create_collection(
        collection_name=OFFER_COLLECTION,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    )
    print("Collections setup complete.")

def index_influencers(client, embeddings):
    influencers = Influencer.objects.all()
    print(f"Indexing {influencers.count()} influencers...")
    
    documents = []
    metadatas = []
    
    for inf in influencers:
        # Construct semantic text
        interests = ", ".join(inf.centres_interet) if isinstance(inf.centres_interet, list) else ""
        content_types = ", ".join(inf.type_contenu) if isinstance(inf.type_contenu, list) else ""
        categories = ", ".join([c.name for c in inf.selected_categories.all()])
        
        text = f"Pseudo: {inf.pseudo or ''}\nBiography: {inf.biography or ''}\nInterests: {interests}\nContent Types: {content_types}\nCategories: {categories}"
        
        documents.append(text)
        metadatas.append({
            "influencer_id": inf.id,
            "pseudo": inf.pseudo,
            "followers": inf.followers_totaux,
            "engagement": inf.engagement_moyen_global,
            "location": inf.localisation,
            "categories": [c.name for c in inf.selected_categories.all()]
        })
    
    if documents:
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=INFLUENCER_COLLECTION,
            embedding=embeddings,
        )
        vector_store.add_texts(texts=documents, metadatas=metadatas)
        print(f"Indexed {len(documents)} influencers.")

def index_offers(client, embeddings):
    offers = Offer.objects.all()
    print(f"Indexing {offers.count()} offers...")
    
    documents = []
    metadatas = []
    
    for offer in offers:
        text = f"Title: {offer.title}\nRequirement: {offer.requirement}\nObjective: {offer.objectif}"
        
        documents.append(text)
        metadatas.append({
            "offer_id": offer.id,
            "min_budget": float(offer.min_budget),
            "max_budget": float(offer.max_budget),
            "influencer_number": offer.influencer_number,
            "created_by_id": offer.created_by.id
        })
        
    if documents:
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=OFFER_COLLECTION,
            embedding=embeddings,
        )
        vector_store.add_texts(texts=documents, metadatas=metadatas)
        print(f"Indexed {len(documents)} offers.")

def run_indexing():
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    setup_collections(client)
    index_influencers(client, embeddings)
    index_offers(client, embeddings)
    print("Recommendation indexing complete!")

if __name__ == "__main__":
    run_indexing()
