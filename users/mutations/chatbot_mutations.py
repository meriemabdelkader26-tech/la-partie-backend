import graphene
from graphql import GraphQLError
from ..chatbot_service import generate_chatbot_reply


class AskChatbot(graphene.Mutation):
    """Role-aware chatbot for company and influencer users."""

    answer = graphene.String()
    intent = graphene.String()
    confidence = graphene.Float()
    suggestions = graphene.List(graphene.String)
    requires_human_support = graphene.Boolean()

    class Arguments:
        question = graphene.String(required=True)
        role = graphene.String(required=False)

    @classmethod
    def mutate(cls, root, info, question, role=None):
        user = info.context.user
        
        # Handle anonymous users or users without a role
        user_role = None
        if user and user.is_authenticated:
            user_role = getattr(user, 'role', None)
            
        # Prioritize the provided role argument, then the user's saved role, 
        # then default to INFLUENCER if unauthenticated.
        effective_role = (role or user_role or "INFLUENCER").upper()

        if effective_role not in {"COMPANY", "INFLUENCER", "ADMIN"}:
            raise GraphQLError("Invalid role for chatbot.")

        reply = generate_chatbot_reply(question=question, role=effective_role)
        return AskChatbot(
            answer=reply.answer,
            intent=reply.intent,
            confidence=reply.confidence,
            suggestions=reply.suggestions,
            requires_human_support=reply.requires_human_support,
        )
