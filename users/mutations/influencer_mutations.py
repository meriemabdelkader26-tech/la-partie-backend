import graphene
from .influencer_mutations_all import (
    CompleteInfluencerProfile,
    ReseauSocialInput,
    InfluencerWorkInput,
    ImageInput,
    InstagramReelInput,
    CarouselMediaInput,
    InstagramPostInput,
    PortfolioMediaInput,
    OffreCollaborationInput,
    InstagramDataInput,
    UpdateInfluencerAvailability,
    UpdateInfluencerProfilePartial
)


class InfluencerMutations(graphene.ObjectType):
    """All influencer mutations in one place"""
    
    complete_influencer_profile = CompleteInfluencerProfile.Field()
    update_influencer_availability = UpdateInfluencerAvailability.Field()
    update_influencer_profile_partial = UpdateInfluencerProfilePartial.Field()


# Export input types for use in other modules
__all__ = [
    'InfluencerMutations',
    'CompleteInfluencerProfile',
    'ReseauSocialInput',
    'InfluencerWorkInput',
    'ImageInput',
    'InstagramReelInput',
    'CarouselMediaInput',
    'InstagramPostInput',
    'PortfolioMediaInput',
    'OffreCollaborationInput',
    'InstagramDataInput',
]

