import graphene
from decimal import Decimal, InvalidOperation

from graphql import GraphQLError

from .offer_mutations_all import (
    OfferCreateMutation,
    OfferUpdateMutation,
    OfferPatchMutation,
    OfferDeleteMutation,
    OfferBatchCreateMutation,
    OfferBatchDeleteMutation
)
from offer.models import Offer
from offer.types.Offer_Node import OfferNode
from users.utils import check_user_role
from users.billing import get_user_quota_snapshot


class CreateOffer(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        min_budget = graphene.Float(required=True)
        max_budget = graphene.Float(required=True)
        start_date = graphene.Date(required=True)
        end_date = graphene.Date(required=True)
        influencer_number = graphene.Int(required=True)
        requirement = graphene.String(required=True)
        objectif = graphene.String(required=True)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    errors = graphene.List(graphene.String)
    offer = graphene.Field(OfferNode)

    def mutate(
        self,
        info,
        title,
        min_budget,
        max_budget,
        start_date,
        end_date,
        influencer_number,
        requirement,
        objectif,
    ):
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        if not (check_user_role(user, "COMPANY") or user.is_staff or user.is_superuser):
            raise GraphQLError("Only company accounts can create offers.")

        validation_errors = []

        try:
            min_budget_decimal = Decimal(str(min_budget))
            max_budget_decimal = Decimal(str(max_budget))
        except (InvalidOperation, ValueError, TypeError):
            return CreateOffer(
                success=False,
                message="Validation failed.",
                errors=["Invalid budget format."],
                offer=None,
            )

        if min_budget_decimal <= 0 or max_budget_decimal <= 0:
            validation_errors.append("Budgets must be greater than zero.")

        if min_budget_decimal > max_budget_decimal:
            validation_errors.append("Minimum budget must be less than or equal to maximum budget.")

        if start_date >= end_date:
            validation_errors.append("End date must be after start date.")

        if influencer_number <= 0:
            validation_errors.append("Influencer number must be greater than zero.")

        if validation_errors:
            return CreateOffer(
                success=False,
                message="Validation failed.",
                errors=validation_errors,
                offer=None,
            )

        quota_snapshot = get_user_quota_snapshot(user)
        if not quota_snapshot.can_create_campaign:
            return CreateOffer(
                success=False,
                message=quota_snapshot.campaign_block_message or "Campaign limit reached.",
                errors=[quota_snapshot.campaign_block_message or "Campaign limit reached."],
                offer=None,
            )

        offer = Offer.objects.create(
            title=title,
            min_budget=min_budget_decimal,
            max_budget=max_budget_decimal,
            start_date=start_date,
            end_date=end_date,
            influencer_number=influencer_number,
            requirement=requirement,
            objectif=objectif,
            created_by=user,
        )

        return CreateOffer(
            success=True,
            message="Offer created successfully.",
            errors=[],
            offer=offer,
        )

class OfferMutations(graphene.ObjectType):
    create_offer = CreateOffer.Field()
    offerCreate = OfferCreateMutation.Field()
    offerUpdate = OfferUpdateMutation.Field()
    offerPatch = OfferPatchMutation.Field()
    offerDelete = OfferDeleteMutation.Field()
    offerBatchCreate = OfferBatchCreateMutation.Field()
    offerBatchDelete = OfferBatchDeleteMutation.Field()
