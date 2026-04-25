import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from common.ai_utils import refine_company_description

class RefineCompanyDescriptionMutation(graphene.Mutation):
    """
    Refines company description using AI.
    """
    class Arguments:
        description = graphene.String(required=True)

    refined_description = graphene.String()

    @classmethod
    @login_required
    def mutate(cls, root, info, description):
        try:
            refined = refine_company_description(description)
            return cls(refined_description=refined)
        except Exception as e:
            raise GraphQLError(f"AI Refinement failed: {str(e)}")
