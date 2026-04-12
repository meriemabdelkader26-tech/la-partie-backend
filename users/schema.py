import graphene



from offer.mutations.offer_mutations import OfferMutations

from offer.queries.offer_queries import OfferQueries

from .queries.user_queries import UserQueries

from .queries.influencer_queries import InfluencerQueries

from .queries.company_queries import CompanyQueries

from .queries.messages_queries import MessagesQueries

from .queries.admin_dashboard_queries import AdminDashboardQueries

from .mutations.user_mutations import UserMutations

from .mutations.auth_mutations import AuthMutations

from .mutations.influencer_mutations import InfluencerMutations

from .mutations.company_mutations import CompanyMutations

from .mutations.messages_mutations import MessagesMutations





class Query(UserQueries, InfluencerQueries, CompanyQueries, MessagesQueries, OfferQueries, AdminDashboardQueries, graphene.ObjectType):

    """Users app queries (with admin dashboard)"""

    pass





class Mutation(UserMutations, AuthMutations, InfluencerMutations, CompanyMutations, MessagesMutations, OfferMutations, graphene.ObjectType):

    """Users app mutations"""

    register_user = UserMutations.register_user





schema = graphene.Schema(query=Query, mutation=Mutation)

