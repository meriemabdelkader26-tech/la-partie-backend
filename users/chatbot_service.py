"""Simple role-aware chatbot service for InfluBridge users."""

from dataclasses import dataclass
from typing import List


@dataclass
class ChatbotReply:
	answer: str
	intent: str
	confidence: float
	suggestions: List[str]
	requires_human_support: bool = False


COMMON_KNOWLEDGE = {
	"verification": {
		"keywords": ["code", "verification", "verifier", "email", "otp", "6 chiffres"],
		"answer": (
			"Pour verifier votre compte, utilisez le code a 6 chiffres recu par email. "
			"S'il expire, utilisez la fonctionnalite de renvoi du code."
		),
	},
	"login": {
		"keywords": ["login", "connexion", "se connecter", "mot de passe", "token"],
		"answer": (
			"Pour vous connecter, utilisez votre email et mot de passe. "
			"Assurez-vous que votre email est verifie avant la connexion."
		),
	},
	"security": {
		"keywords": ["securite", "hack", "pirate", "compte bloque", "banned"],
		"answer": (
			"En cas de probleme de securite, changez le mot de passe immediatement et contactez le support. "
			"Les comptes bannis doivent etre revus par un administrateur."
		),
	},
}


ROLE_KNOWLEDGE = {
	"COMPANY": {
		"campaign": {
			"keywords": ["campagne", "offre", "budget", "brief", "marque"],
			"answer": (
				"En tant que marque, creez une offre claire avec objectif, budget et delai. "
				"Plus le brief est precis, plus les candidatures des influenceurs seront pertinentes."
			),
		},
		"matching": {
			"keywords": ["recommandation", "matching", "trouver influenceur", "selection"],
			"answer": (
				"Utilisez les filtres categorie, pays et performance pour shortlist vos influenceurs. "
				"Comparez le taux d'engagement et l'historique des collaborations avant validation."
			),
		},
		"billing": {
			"keywords": ["paiement", "facture", "billing", "tarif", "cout"],
			"answer": (
				"Validez le tarif dans l'offre puis suivez les etapes de collaboration. "
				"Conservez un recapitulatif des livrables pour faciliter la facturation."
			),
		},
	},
	"INFLUENCER": {
		"profile": {
			"keywords": ["profil", "portfolio", "bio", "reseau", "instagram"],
			"answer": (
				"Pour augmenter vos chances, completez votre profil: niche, audience, statistiques et portfolio. "
				"Un profil detaille est priorise par les marques."
			),
		},
		"application": {
			"keywords": ["postuler", "candidature", "offre", "brief", "proposition"],
			"answer": (
				"Quand vous postulez, adaptez votre proposition au brief de la marque, "
				"indiquez votre delai et les formats de contenu proposes."
			),
		},
		"earnings": {
			"keywords": ["revenu", "paiement", "combien", "tarif", "gains"],
			"answer": (
				"Fixez un tarif coherent avec vos performances et vos livrables. "
				"Precisez les revisions incluses pour eviter les incomprehensions."
			),
		},
	},
}


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
	normalized = (question or "").strip().lower()
	normalized_role = (role or "").strip().upper()

	if not normalized:
		return ChatbotReply(
			answer="Posez votre question et je vous aiderai pas a pas.",
			intent="empty",
			confidence=0.0,
			suggestions=_build_suggestions(normalized_role),
		)

	for intent_name, config in COMMON_KNOWLEDGE.items():
		if any(keyword in normalized for keyword in config["keywords"]):
			return ChatbotReply(
				answer=config["answer"],
				intent=intent_name,
				confidence=0.82,
				suggestions=_build_suggestions(normalized_role),
			)

	for intent_name, config in ROLE_KNOWLEDGE.get(normalized_role, {}).items():
		if any(keyword in normalized for keyword in config["keywords"]):
			return ChatbotReply(
				answer=config["answer"],
				intent=intent_name,
				confidence=0.9,
				suggestions=_build_suggestions(normalized_role),
			)

	return ChatbotReply(
		answer=(
			"Je n'ai pas encore une reponse certaine a cette question. "
			"Reformulez avec plus de details (objectif, role, blocage), "
			"ou contactez le support pour une assistance humaine."
		),
		intent="fallback",
		confidence=0.35,
		suggestions=_build_suggestions(normalized_role),
		requires_human_support=True,
	)
