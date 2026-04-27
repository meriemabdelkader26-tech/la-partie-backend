import graphene
from decimal import Decimal, InvalidOperation
from graphql_relay import from_global_id

from graphql import GraphQLError

from .offer_mutations_all import (
    OfferCreateMutation,
    OfferUpdateMutation,
    OfferPatchMutation,
    OfferDeleteMutation,
    OfferBatchCreateMutation,
    OfferBatchDeleteMutation
)
from .ai_mutations import RefineRequirementsMutation
from django.contrib.auth import get_user_model
from offer.models import Offer, SavedOffer
from offer.types.Offer_Node import OfferNode
from users.utils import check_user_role, safe_create_notification
from users.models import NotificationType
from users.billing import get_user_quota_snapshot

User = get_user_model()


class SaveOffer(graphene.Mutation):
    class Arguments:
        offer_id = graphene.ID(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    offer = graphene.Field(OfferNode)

    def mutate(self, info, offer_id):
        user = info.context.user
        if not user.is_authenticated:
            raise GraphQLError("Authentication required")

        try:
            node_type, pk = from_global_id(offer_id)
            if node_type == 'OfferNode':
                offer_id = int(pk)
            else:
                offer_id = int(offer_id)
        except Exception:
            try:
                offer_id = int(offer_id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid offer ID format.")

        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            raise GraphQLError("Offer not found")

        saved_offer, created = SavedOffer.objects.get_or_create(user=user, offer=offer)

        if not created:
            saved_offer.delete()
            return SaveOffer(success=True, message="Offer unsaved successfully", offer=offer)

        return SaveOffer(success=True, message="Offer saved successfully", offer=offer)


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

        if not (check_user_role(user, "COMPANY") or user.is_staff or user.is_admin or user.is_superuser):
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

        # Notify influencers about the new offer
        influencers = User.objects.filter(role='INFLUENCER')
        for influencer in influencers:
            safe_create_notification(
                user=influencer,
                notification_type=NotificationType.SYSTEM,
                title="New Campaign Available",
                message=f"A new campaign '{title}' has been posted. Apply now!",
                link=f"/influencer/campaigns"
            )

        # Notify admins about the new offer
        admins = User.objects.filter(role='ADMIN') | User.objects.filter(is_staff=True)
        for admin in admins.distinct():
            safe_create_notification(
                user=admin,
                notification_type=NotificationType.SYSTEM,
                title="New Campaign Created",
                message=f"A new campaign '{title}' has been created by {user.name or user.email}.",
                link=f"/admin/offer"
            )

        return CreateOffer(
            success=True,
            message="Offer created successfully.",
            errors=[],
            offer=offer,
        )

class UpdateOffer(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        title = graphene.String()
        min_budget = graphene.Float()
        max_budget = graphene.Float()
        start_date = graphene.Date()
        end_date = graphene.Date()
        influencer_number = graphene.Int()
        requirement = graphene.String()
        objectif = graphene.String()

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    errors = graphene.List(graphene.String)
    offer = graphene.Field(OfferNode)

    def mutate(
        self,
        info,
        id,
        title=None,
        min_budget=None,
        max_budget=None,
        start_date=None,
        end_date=None,
        influencer_number=None,
        requirement=None,
        objectif=None,
    ):
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        try:
            node_type, pk = from_global_id(id)
            if node_type == 'OfferNode':
                offer_id = int(pk)
            else:
                offer_id = int(id)
        except Exception:
            try:
                offer_id = int(id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid offer ID format.")

        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return UpdateOffer(
                success=False,
                message="Offer not found.",
                errors=["Offer not found."],
                offer=None,
            )

        # Check permissions: owner or admin
        if not (offer.created_by == user or user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("You do not have permission to update this offer.")

        validation_errors = []

        if min_budget is not None or max_budget is not None:
            curr_min = Decimal(str(min_budget)) if min_budget is not None else offer.min_budget
            curr_max = Decimal(str(max_budget)) if max_budget is not None else offer.max_budget
            
            if curr_min <= 0 or curr_max <= 0:
                validation_errors.append("Budgets must be greater than zero.")
            if curr_min > curr_max:
                validation_errors.append("Minimum budget must be less than or equal to maximum budget.")

        if start_date is not None or end_date is not None:
            curr_start = start_date if start_date is not None else offer.start_date
            curr_end = end_date if end_date is not None else offer.end_date
            if curr_start >= curr_end:
                validation_errors.append("End date must be after start date.")

        if influencer_number is not None and influencer_number <= 0:
            validation_errors.append("Influencer number must be greater than zero.")

        if validation_errors:
            return UpdateOffer(
                success=False,
                message="Validation failed.",
                errors=validation_errors,
                offer=None,
            )

        # Update fields
        if title is not None:
            offer.title = title
        if min_budget is not None:
            offer.min_budget = Decimal(str(min_budget))
        if max_budget is not None:
            offer.max_budget = Decimal(str(max_budget))
        if start_date is not None:
            offer.start_date = start_date
        if end_date is not None:
            offer.end_date = end_date
        if influencer_number is not None:
            offer.influencer_number = influencer_number
        if requirement is not None:
            offer.requirement = requirement
        if objectif is not None:
            offer.objectif = objectif

        offer.save()

        return UpdateOffer(
            success=True,
            message="Offer updated successfully.",
            errors=[],
            offer=offer,
        )

class DeleteOffer(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(self, info, id):
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError("You must be logged in.")

        try:
            node_type, pk = from_global_id(id)
            if node_type == 'OfferNode':
                offer_id = int(pk)
            else:
                offer_id = int(id)
        except Exception:
            try:
                offer_id = int(id)
            except (ValueError, TypeError):
                raise GraphQLError("Invalid offer ID format.")

        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return DeleteOffer(
                success=False,
                message="Offer not found."
            )

        # Check permissions: owner or admin
        if not (offer.created_by == user or user.is_staff or user.is_admin or user.is_superuser):
            raise GraphQLError("You do not have permission to delete this offer.")

        offer.delete()

        return DeleteOffer(
            success=True,
            message="Offer deleted successfully."
        )

class OfferMutations(graphene.ObjectType):
    save_offer = SaveOffer.Field()
    create_offer = CreateOffer.Field()
    update_offer = UpdateOffer.Field()
    delete_offer = DeleteOffer.Field()
    offerCreate = OfferCreateMutation.Field()
    offerUpdate = OfferUpdateMutation.Field()
    offerPatch = OfferPatchMutation.Field()
    offerDelete = OfferDeleteMutation.Field()
    offerBatchCreate = OfferBatchCreateMutation.Field()
    offerBatchDelete = OfferBatchDeleteMutation.Field()
    refineRequirements = RefineRequirementsMutation.Field()
