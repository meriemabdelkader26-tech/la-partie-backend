import graphene
from .company_mutations_all import (
    CreateCompanyProfile,
    UpdateCompanyProfile,
    AddCompanyImage,
    RemoveCompanyImage,
    CompleteCompanyProfile,
    UpdateCompanyAvailability,
    AddressInput,
    CompanyImageInput
)


class CompanyMutations(graphene.ObjectType):
    """All company mutations in one place"""
    
    create_company_profile = CreateCompanyProfile.Field()
    update_company_profile = UpdateCompanyProfile.Field()
    update_company_availability = UpdateCompanyAvailability.Field()
    add_company_image = AddCompanyImage.Field()
    remove_company_image = RemoveCompanyImage.Field()
    complete_company_profile = CompleteCompanyProfile.Field()


# Export input types for use in other modules
__all__ = [
    'CompanyMutations',
    'CreateCompanyProfile',
    'UpdateCompanyProfile',
    'AddCompanyImage',
    'RemoveCompanyImage',
    'CompleteCompanyProfile',
    'AddressInput',
    'CompanyImageInput',
]

