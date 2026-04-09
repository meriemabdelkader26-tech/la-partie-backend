import graphene

from category import schema as category_schema
from users import schema as users_schema
from offer import schema as offer_schema

# IMPORT CORRIGÉ
from offer.mutations.offer_application_mutations import (
    AddPaymentMethod,
    CreateOfferApplication,
    CreatePayoutRequest,
    DeclineOfferOpportunity,
    UpdateOfferApplicationStatus,
    MarkApplicationPaymentEscrow,
    CreateApplicationCheckoutSession,
    ReleaseApplicationPayment,
    RefundApplicationPayment,
)

class Query(
    users_schema.Query,
    category_schema.Query,
    offer_schema.Query,
    graphene.ObjectType
):
    pass


class Mutation(
    users_schema.Mutation,
    category_schema.Mutation,
    offer_schema.Mutation,
    graphene.ObjectType
):
    create_offer_application = CreateOfferApplication.Field()
    add_payment_method = AddPaymentMethod.Field()
    create_payout_request = CreatePayoutRequest.Field()
    decline_offer_opportunity = DeclineOfferOpportunity.Field()
    update_offer_application_status = UpdateOfferApplicationStatus.Field()
    mark_application_payment_escrow = MarkApplicationPaymentEscrow.Field()
    create_application_checkout_session = CreateApplicationCheckoutSession.Field()
    release_application_payment = ReleaseApplicationPayment.Field()
    refund_application_payment = RefundApplicationPayment.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
