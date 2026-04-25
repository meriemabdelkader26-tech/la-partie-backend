import os
import numpy as np
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from django.db.models import Q

# We need access to models
from users.influencer_models import Influencer, Category
from offer.models import Offer

class HybridRecommender:
    def __init__(self):
        self.qdrant_url = "https://73b0fb86-a6a8-45eb-8e70-cc1697987b8a.eu-central-1-0.aws.cloud.qdrant.io:6333"
        self.qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MTU5NTBjZDMtNTUxNy00Y2Q0LTlmNDMtZjgzNzBlNDhkY2ZiIn0.n1xPzYsMFfvbcjFVJdjPuNENFLLjM5tET0-Yr7n9RTw"
        
        self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        self.inf_collection = "influencer_profiles"
        self.offer_collection = "offer_requirements"
        
        # Initialize Gemini for explanations
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.7,
            max_output_tokens=150
        )

    def _get_embedding(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    def generate_explanation(self, match_data: Dict[str, Any], context_type: str) -> str:
        """Generate a natural language explanation for a recommendation using Gemini."""
        if context_type == "offer_for_influencer":
            prompt = f"""
            Generate a short, enthusiastic explanation (1-2 sentences) for why this offer is a good match for an influencer.
            Offer: {match_data['title']}
            Semantic Similarity Score: {match_data['semantic_score']:.2f}
            Category Match: {'Yes' if match_data['category_match'] == 1.0 else 'Partial'}
            Budget Alignment: {'Perfect' if match_data['budget_alignment'] == 1.0 else 'Acceptable'}
            """
        else:
            prompt = f"""
            Generate a short, professional explanation (1-2 sentences) for why this influencer is a good match for a brand's offer.
            Influencer: {match_data['name']} (@{match_data['pseudo']})
            Followers: {match_data['followers']}
            Engagement Score: {match_data['engagement_score']:.2f}
            Semantic Similarity Score: {match_data['semantic_score']:.2f}
            """

        try:
            messages = [
                SystemMessage(content="You are an AI assistant for InfluBridge, helping users understand why they received certain recommendations. Be concise, friendly, and professional."),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            return "Based on your profile and the offer requirements, this is a highly relevant match."

    def recommend_offers_for_influencer(self, influencer_id: int, limit: int = 5, explain: bool = True) -> List[Dict[str, Any]]:
        try:
            influencer = Influencer.objects.get(id=influencer_id)
        except Influencer.DoesNotExist:
            return []

        # 1. Get Influencer Vector
        interests = ", ".join(influencer.centres_interet) if isinstance(influencer.centres_interet, list) else ""
        content_types = ", ".join(influencer.type_contenu) if isinstance(influencer.type_contenu, list) else ""
        categories = ", ".join([c.name for c in influencer.selected_categories.all()])
        
        inf_text = f"Pseudo: {influencer.pseudo or ''}\nBiography: {influencer.biography or ''}\nInterests: {interests}\nContent Types: {content_types}\nCategories: {categories}"
        query_vector = self._get_embedding(inf_text)

        # 2. Semantic Search in Offer Collection
        search_results = self.client.query_points(
            collection_name=self.offer_collection,
            query=query_vector,
            limit=limit * 2, # Fetch more to allow for hybrid ranking
            with_payload=True
        ).points

        recommendations = []
        inf_categories = set(influencer.selected_categories.values_list('name', flat=True))
        
        # Get influencer budget expectations if any
        inf_offer_prices = influencer.offres_collaboration.all()
        min_expected = float(min([o.tarif_minimum for o in inf_offer_prices])) if inf_offer_prices else 0.0
        max_expected = float(max([o.tarif_maximum for o in inf_offer_prices])) if inf_offer_prices else 1000000.0

        for res in search_results:
            offer_id = res.payload.get('offer_id') or res.payload.get('metadata', {}).get('offer_id')
            if not offer_id:
                continue
            try:
                offer = Offer.objects.get(id=offer_id)
            except Offer.DoesNotExist:
                continue

            semantic_sim = res.score # Already cosine similarity [0, 1]
            
            # Category Match (Simple overlap)
            # Since offers don't have explicit categories in the model yet, we might check title/req
            # but let's assume for now we might add categories to Offer or use semantic search for that.
            # For now, let's use a placeholder or semantic similarity covers it.
            category_match = 1.0 if any(cat.lower() in offer.title.lower() or cat.lower() in offer.requirement.lower() for cat in inf_categories) else 0.5

            # Budget Alignment
            # Overlap between [offer.min_budget, offer.max_budget] and [min_expected, max_expected]
            offer_min = float(offer.min_budget)
            offer_max = float(offer.max_budget)
            
            budget_alignment = 0.5
            if (offer_min <= max_expected and offer_max >= min_expected):
                budget_alignment = 1.0
            elif (offer_max < min_expected or offer_min > max_expected):
                budget_alignment = 0.2

            # Final Score Calculation
            final_score = (0.5 * semantic_sim) + (0.3 * category_match) + (0.2 * budget_alignment)

            recommendations.append({
                "offer_id": offer.id,
                "title": offer.title,
                "objectif": offer.objectif,
                "requirement": offer.requirement,
                "score": final_score,
                "semantic_score": semantic_sim,
                "category_match": category_match,
                "budget_alignment": budget_alignment,
                "min_budget": offer_min,
                "max_budget": offer_max,
                "end_date": offer.end_date.isoformat() if offer.end_date else "",
                "influencer_number": offer.influencer_number,
                "created_by_name": offer.created_by.name if offer.created_by else "System"
            })

        # Sort by final score
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        top_recs = recommendations[:limit]
        
        # Add explanations for top results
        if explain:
            for rec in top_recs:
                rec['explanation'] = self.generate_explanation(rec, "offer_for_influencer")
                
        return top_recs

    def recommend_influencers_for_offer(self, offer_id: int, limit: int = 5, explain: bool = True) -> List[Dict[str, Any]]:
        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return []

        # 1. Get Offer Vector
        offer_text = f"Title: {offer.title}\nRequirement: {offer.requirement}\nObjective: {offer.objectif}"
        query_vector = self._get_embedding(offer_text)

        # 2. Semantic Search in Influencer Collection
        search_results = self.client.query_points(
            collection_name=self.inf_collection,
            query=query_vector,
            limit=limit * 2,
            with_payload=True
        ).points

        recommendations = []
        offer_min = float(offer.min_budget)
        offer_max = float(offer.max_budget)

        for res in search_results:
            inf_id = res.payload.get('influencer_id') or res.payload.get('metadata', {}).get('influencer_id')
            if not inf_id:
                continue
            try:
                inf = Influencer.objects.get(id=inf_id)
            except Influencer.DoesNotExist:
                continue

            semantic_sim = res.score
            
            # Engagement Score (Normalized [0, 1])
            # Assuming engagement rate is usually < 20%
            engagement_val = inf.engagement_moyen_global / 20.0 
            engagement_score = min(max(engagement_val, 0.0), 1.0)

            # Category Match
            # Check if offer title/req matches influencer categories
            inf_categories = set(inf.selected_categories.values_list('name', flat=True))
            category_match = 1.0 if any(cat.lower() in offer.title.lower() or cat.lower() in offer.requirement.lower() for cat in inf_categories) else 0.5

            # Budget Alignment
            inf_offer_prices = inf.offres_collaboration.all()
            inf_min = float(min([o.tarif_minimum for o in inf_offer_prices])) if inf_offer_prices else 0.0
            inf_max = float(max([o.tarif_maximum for o in inf_offer_prices])) if inf_offer_prices else 1000000.0
            
            budget_alignment = 0.5
            if (inf_min <= offer_max and inf_max >= offer_min):
                budget_alignment = 1.0
            elif (inf_max < offer_min or inf_min > offer_max):
                budget_alignment = 0.2

            # Final Score: (0.4 * SemanticSimilarity) + (0.3 * Engagement) + (0.2 * CategoryMatch) + (0.1 * BudgetAlignment)
            final_score = (0.4 * semantic_sim) + (0.3 * engagement_score) + (0.2 * category_match) + (0.1 * budget_alignment)

            recommendations.append({
                "influencer_id": inf.id,
                "name": inf.user.name,
                "pseudo": inf.pseudo,
                "score": final_score,
                "semantic_score": semantic_sim,
                "engagement_score": engagement_score,
                "category_match": category_match,
                "budget_alignment": budget_alignment,
                "followers": inf.followers_totaux
            })

        # Sort by final score
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        top_recs = recommendations[:limit]
        
        # Add explanations for top results
        if explain:
            for rec in top_recs:
                rec['explanation'] = self.generate_explanation(rec, "influencer_for_offer")
                
        return top_recs

# Singleton instance
_recommender = None

def get_hybrid_recommender():
    global _recommender
    if _recommender is None:
        _recommender = HybridRecommender()
    return _recommender
