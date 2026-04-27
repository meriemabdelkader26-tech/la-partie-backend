import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from common.ai_utils import refine_campaign_requirements

class RefineRequirementsMutation(graphene.Mutation):
    """
    Refines campaign requirements using AI.
    """
    class Arguments:
        requirements = graphene.String(required=True)

    refined_requirements = graphene.String()

    @classmethod
    @login_required
    def mutate(cls, root, info, requirements):
        user = info.context.user
        if not (user.is_staff or user.is_admin or getattr(user, 'is_superuser', False)):
            raise GraphQLError("Admin privileges required")

        try:
            refined = refine_campaign_requirements(requirements)
            return cls(refined_requirements=refined)
        except Exception as e:
            raise GraphQLError(f"AI Refinement failed: {str(e)}")
