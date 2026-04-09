import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

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

    @login_required
    def mutate(self, info, question, role=None):
        user = info.context.user
        effective_role = (role or user.role or "").upper()

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
