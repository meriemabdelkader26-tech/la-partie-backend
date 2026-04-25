"""Role-aware RAG chatbot service for InfluBridge users powered by Gemini."""

from dataclasses import dataclass
from typing import List, Optional
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

# Load environment variables
load_dotenv()

# RAG Configuration
QDRANT_URL = "https://73b0fb86-a6a8-45eb-8e70-cc1697987b8a.eu-central-1-0.aws.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MTU5NTBjZDMtNTUxNy00Y2Q0LTlmNDMtZjgzNzBlNDhkY2ZiIn0.n1xPzYsMFfvbcjFVJdjPuNENFLLjM5tET0-Yr7n9RTw"
COLLECTION_NAME = "influbridge_faq"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

@dataclass
class ChatbotReply:
    answer: str
    intent: str
    confidence: float
    suggestions: List[str]
    requires_human_support: bool = False

class RAGChatbotService:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=COLLECTION_NAME,
            embedding=self.embeddings,
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.3,
        )
        self.prompt = PromptTemplate(
            input_variables=["context", "question", "role"],
            template="""You are a helpful and professional assistant for InfluBridge, an influencer marketing platform. 
Your goal is to provide accurate, friendly, and role-appropriate assistance.
The user is logged in with the role: {role}.

Instructions:
1. Use the provided context from our FAQ database to answer the question.
2. If the context contains a specific answer, prioritize it.
3. If the context is empty or doesn't have the answer, use your general knowledge to help the user, but stay within the scope of an influencer marketing platform.
4. If you are really unsure, advise the user to contact support.
5. Keep your tone professional, encouraging, and clear.

Context from FAQ:
{context}

User Question: {question}
Helpful Answer:"""
        )
        
    def query(self, question: str, role: str) -> Optional[str]:
        # Search for relevant documents in Qdrant
        try:
            # Construct Qdrant filter
            qdrant_filter = rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="actor",
                        match=rest.MatchValue(value=role),
                    )
                ]
            )
            
            search_results = self.vector_store.similarity_search(
                question, 
                k=3,
                filter=qdrant_filter
            )
            
            if not search_results:
                # Try without filter if no results for specific role
                search_results = self.vector_store.similarity_search(question, k=3)
        except Exception as e:
            print(f"Vector search error: {e}")
            # Fallback to search without filter if filter fails
            try:
                search_results = self.vector_store.similarity_search(question, k=3)
            except:
                search_results = []
            
        # Prepare context from search results
        context = ""
        if search_results:
            context = "\n---\n".join([
                f"Topic: {doc.metadata.get('question', 'General')}\nInformation: {doc.metadata.get('answer', doc.page_content)}"
                for doc in search_results
            ])
        
        # Generate answer using Gemini
        try:
            chain = self.prompt | self.llm
            response = chain.invoke({
                "context": context if context else "No specific FAQ entries found for this query.",
                "question": question,
                "role": role
            })
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            print(f"Gemini generation error: {e}")
            return None

# Singleton instance
_rag_service = None

def get_rag_service():
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGChatbotService()
    return _rag_service

DEFAULT_SUGGESTIONS = [
    "Comment verifier mon email ?",
    "Comment securiser mon compte ?",
    "Comment contacter le support ?",
]


def _build_suggestions(role: str) -> List[str]:
    if role == "COMPANY":
        return [
            "Comment creer une offre efficace ?",
            "Comment choisir un influenceur ?",
            "Comment gerer budget et livrables ?",
        ]
    if role == "INFLUENCER":
        return [
            "Comment ameliorer mon profil ?",
            "Comment repondre a une offre ?",
            "Comment fixer mon tarif ?",
        ]
    return DEFAULT_SUGGESTIONS


def generate_chatbot_reply(question: str, role: str) -> ChatbotReply:
    normalized = (question or "").strip()
    normalized_role = (role or "").strip().upper()

    if not normalized:
        return ChatbotReply(
            answer="Posez votre question et je vous aiderai pas a pas.",
            intent="empty",
            confidence=0.0,
            suggestions=_build_suggestions(normalized_role),
        )

    # Try RAG with Gemini
    try:
        rag_service = get_rag_service()
        gemini_answer = rag_service.query(normalized, normalized_role)
        
        if gemini_answer:
            return ChatbotReply(
                answer=gemini_answer,
                intent="gemini_response",
                confidence=0.95,
                suggestions=_build_suggestions(normalized_role),
            )
    except Exception as e:
        print(f"Chatbot Service Error: {e}")
        # If RAG fails, we'll try a very simple fallback below

    # Last resort fallback if Gemini/RAG failed
    return ChatbotReply(
        answer=(
            "Désolé, j'ai rencontré une petite difficulté technique. "
            "Pouvez-vous reformuler votre question ou essayer plus tard ? "
            "Sinon, contactez notre support."
        ),
        intent="error_fallback",
        confidence=0.1,
        suggestions=_build_suggestions(normalized_role),
        requires_human_support=True,
    )
