import graphene
from offer.types.Offer_Node import OfferNode
from offer.models import Offer
from graphql import GraphQLError
from graphql_relay import from_global_id

class OfferSingleQuery(graphene.ObjectType):
    """Query to get a single offer by ID"""
    
    offer = graphene.Field(OfferNode, id=graphene.ID(required=True))

    def resolve_offer(self, info, id):
        """Resolve a single offer by either global ID or database ID"""
        if not id:
            return None

        # 1. Try to treat as Global ID
        try:
            from graphql_relay import from_global_id
            try:
                node_type, pk = from_global_id(id)
                # Some Graphene versions might return node_type as 'Offer' instead of 'OfferNode'
                if node_type in ['OfferNode', 'Offer']:
                    offer = Offer.objects.filter(pk=pk).first()
                    if offer:
                        return offer
            except Exception:
                pass
        except Exception:
            pass

        # 2. Try to treat as plain database ID
        try:
            # Handle numeric strings
            if isinstance(id, str) and id.isdigit():
                offer = Offer.objects.filter(pk=int(id)).first()
                if offer:
                    return offer
            
            # Try direct filter
            return Offer.objects.filter(pk=id).first()
        except (ValueError, TypeError, Exception):
            pass
            
        return None
