"""
Consolidated Company Mutations
All company-related operations including profile creation, updates, and image management
"""
import graphene
from graphene import InputObjectType
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from users.models import User, UserRole
from users.company_models import Company, Address
from users.influencer_models import Image
from users.types.company_node import CompanyNode, AddressNode
from users.user_node import UserNode


def is_company_role(user):
    """Helper function to check if user has COMPANY role"""
    if not user or not user.is_authenticated:
        return False
    user_role = str(user.role)
    return 'COMPANY' in user_role or user.role == UserRole.COMPANY.value


class AddressInput(InputObjectType):
    """Input type for Address"""
    address = graphene.String(required=True)
    city = graphene.String(required=True)
    state = graphene.String()
    postal_code = graphene.String()
    country = graphene.String(required=True)


class CompanyImageInput(InputObjectType):
    """Input type for Company Images"""
    url = graphene.String(required=True)
    is_default = graphene.Boolean(default_value=False)
    is_public = graphene.Boolean(default_value=True)


class CreateCompanyProfile(graphene.Mutation):
    """Create a company profile for a user with COMPANY role"""
    
    class Arguments:
        company_name = graphene.String(required=True)
        matricule = graphene.String()
        website = graphene.String()
        size = graphene.String()
        description = graphene.String()
        domain_activity = graphene.String()
        contact_email = graphene.String()
        entreprise_type = graphene.String()
        langues = graphene.List(graphene.String)
        disponibilite_collaboration = graphene.String()
        address = AddressInput()
        images = graphene.List(CompanyImageInput)
    
    success = graphene.Boolean()
    message = graphene.String()
    company = graphene.Field(CompanyNode)
    user = graphene.Field(UserNode)
    
    @staticmethod
    @transaction.atomic
    def mutate(root, info, company_name, **kwargs):
        user = info.context.user
        
        if not user.is_authenticated:
            return CreateCompanyProfile(
                success=False,
                message="Authentication required",
                company=None,
                user=None
            )
        
        if not is_company_role(user):
            return CreateCompanyProfile(
                success=False,
                message=f"User must have COMPANY role to create a company profile. Current role: {user.role}",
                company=None,
                user=None
            )
        
        if hasattr(user, 'company_profile'):
            return CreateCompanyProfile(
                success=False,
                message="Company profile already exists for this user",
                company=None,
                user=user
            )
        
        # Create address if provided
        address_obj = None
        if 'address' in kwargs and kwargs['address']:
            address_data = kwargs.pop('address')
            address_obj = Address.objects.create(
                address=address_data.address,
                city=address_data.city,
                state=address_data.get('state'),
                postal_code=address_data.get('postal_code'),
                country=address_data.country
            )
        
        # Extract images data before creating company
        images_data = kwargs.pop('images', [])
        
        # Create company profile
        company = Company.objects.create(
            user=user,
            company_name=company_name,
            address=address_obj,
            **kwargs
        )
        
        # Create images if provided
        if images_data:
            content_type = ContentType.objects.get_for_model(Company)
            for img_data in images_data:
                Image.objects.create(
                    url=img_data.url,
                    is_default=img_data.get('is_default', False),
                    is_public=img_data.get('is_public', True),
                    content_type=content_type,
                    object_id=company.id
                )

        # Mark profile as completed after first successful company profile creation
        user.is_completed_profile = True
        user.save(update_fields=['is_completed_profile'])
        
        return CreateCompanyProfile(
            success=True,
            message="Company profile created successfully",
            company=company,
            user=user
        )


class UpdateCompanyProfile(graphene.Mutation):
    """Update an existing company profile"""
    
    class Arguments:
        company_name = graphene.String()
        matricule = graphene.String()
        website = graphene.String()
        size = graphene.String()
        description = graphene.String()
        domain_activity = graphene.String()
        contact_email = graphene.String()
        entreprise_type = graphene.String()
        langues = graphene.List(graphene.String)
        disponibilite_collaboration = graphene.String()
        address = AddressInput()
    
    success = graphene.Boolean()
    message = graphene.String()
    company = graphene.Field(CompanyNode)
    
    @staticmethod
    @transaction.atomic
    def mutate(root, info, **kwargs):
        user = info.context.user
        
        if not user.is_authenticated:
            return UpdateCompanyProfile(
                success=False,
                message="Authentication required",
                company=None
            )
        
        if not hasattr(user, 'company_profile'):
            return UpdateCompanyProfile(
                success=False,
                message="Company profile does not exist for this user",
                company=None
            )
        
        company = user.company_profile
        
        # Update address if provided
        if 'address' in kwargs and kwargs['address']:
            address_data = kwargs.pop('address')
            
            if company.address:
                # Update existing address
                for key, value in address_data.items():
                    if value is not None:
                        setattr(company.address, key, value)
                company.address.save()
            else:
                # Create new address
                address_obj = Address.objects.create(
                    address=address_data.address,
                    city=address_data.city,
                    state=address_data.get('state'),
                    postal_code=address_data.get('postal_code'),
                    country=address_data.country
                )
                company.address = address_obj
        
        # Update company fields
        for key, value in kwargs.items():
            if value is not None:
                setattr(company, key, value)
        
        company.save()
        
        return UpdateCompanyProfile(
            success=True,
            message="Company profile updated successfully",
            company=company
        )


class AddCompanyImage(graphene.Mutation):
    """Add an image to company profile"""
    
    class Arguments:
        url = graphene.String(required=True)
        is_default = graphene.Boolean(default_value=False)
        is_public = graphene.Boolean(default_value=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    image = graphene.Field('users.types.company_node.CompanyImageNode')
    
    @staticmethod
    def mutate(root, info, url, is_default=False, is_public=True):
        user = info.context.user
        
        if not user.is_authenticated:
            return AddCompanyImage(
                success=False,
                message="Authentication required",
                image=None
            )
        
        if not hasattr(user, 'company_profile'):
            return AddCompanyImage(
                success=False,
                message="Company profile does not exist for this user",
                image=None
            )
        
        company = user.company_profile
        content_type = ContentType.objects.get_for_model(Company)
        
        # Create the image
        image = Image.objects.create(
            url=url,
            is_default=is_default,
            is_public=is_public,
            content_type=content_type,
            object_id=company.id
        )
        
        return AddCompanyImage(
            success=True,
            message="Image added successfully",
            image=image
        )


class RemoveCompanyImage(graphene.Mutation):
    """Remove an image from company profile"""
    
    class Arguments:
        image_id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    @staticmethod
    def mutate(root, info, image_id):
        user = info.context.user
        
        if not user.is_authenticated:
            return RemoveCompanyImage(
                success=False,
                message="Authentication required"
            )
        
        if not hasattr(user, 'company_profile'):
            return RemoveCompanyImage(
                success=False,
                message="Company profile does not exist for this user"
            )
        
        company = user.company_profile
        
        try:
            image = Image.objects.get(
                id=image_id,
                content_type=ContentType.objects.get_for_model(Company),
                object_id=company.id
            )
            image.delete()
            
            return RemoveCompanyImage(
                success=True,
                message="Image removed successfully"
            )
        except Image.DoesNotExist:
            return RemoveCompanyImage(
                success=False,
                message="Image not found"
            )


class CompleteCompanyProfile(graphene.Mutation):
    """Mark company profile as completed"""
    
    success = graphene.Boolean()
    message = graphene.String()
    company = graphene.Field(CompanyNode)
    
    @staticmethod
    def mutate(root, info):
        user = info.context.user
        
        if not user.is_authenticated:
            return CompleteCompanyProfile(
                success=False,
                message="Authentication required",
                company=None
            )
        
        if not hasattr(user, 'company_profile'):
            return CompleteCompanyProfile(
                success=False,
                message="Company profile does not exist for this user",
                company=None
            )
        
        company = user.company_profile
        
        # Validate required fields
        if not company.company_name:
            return CompleteCompanyProfile(
                success=False,
                message="Company name is required to complete profile",
                company=None
            )
        
        if not company.address:
            return CompleteCompanyProfile(
                success=False,
                message="Address is required to complete profile",
                company=None
            )
        
        # Mark profile as completed
        user.is_completed_profile = True
        user.save(update_fields=['is_completed_profile'])
        
        return CompleteCompanyProfile(
            success=True,
            message="Company profile completed successfully",
            company=company
        )
