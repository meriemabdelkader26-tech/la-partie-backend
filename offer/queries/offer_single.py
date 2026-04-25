import graphene
from offer.types.Offer_Node import OfferNode
from offer.models import Offer
from graphql import GraphQLError

class OfferSingleQuery(graphene.ObjectType):
    """Query to get a single offer by ID"""
    
    offer = graphene.Field(OfferNode, id=graphene.ID(required=True))

    def resolve_offer(self, info, id):
        """Resolve a single offer by either global ID or database ID"""
        # 1. Try to treat as Global ID
        try:
            from graphene import relay
            node_type, pk = relay.Node.from_global_id(id)
            if node_type == 'OfferNode':
                return Offer.objects.filter(pk=pk).first()
        except Exception:
            pass

        # 2. Try to treat as plain database ID
        try:
            return Offer.objects.filter(pk=id).first()
        except (ValueError, TypeError):
            return None
