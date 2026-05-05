import graphene
from graphene_django import DjangoObjectType
from users.company_models import Company, Address
from users.influencer_models import Image


class AddressNode(DjangoObjectType):
    """GraphQL type for Address"""
    
    class Meta:
        model = Address
        fields = (
            'id',
            'address',
            'city',
            'state',
            'postal_code',
            'country',
            'created_at',
            'updated_at',
        )


class CompanyImageNode(DjangoObjectType):
    """GraphQL type for Company Images"""
    
    class Meta:
        model = Image
        fields = (
            'id',
            'url',
            'is_default',
            'is_public',
            'created_at',
        )


class CompanyNode(DjangoObjectType):
    """GraphQL type for Company"""
    
    images = graphene.List(CompanyImageNode)
    address = graphene.Field(AddressNode)
    disponibilite_collaboration = graphene.Field('users.influencer_node.DisponibiliteEnum')
    
    class Meta:
        model = Company
        fields = (
            'id',
            'user',
            'company_name',
            'matricule',
            'website',
            'size',
            'description',
            'domain_activity',
            'contact_email',
            'entreprise_type',
            'address',
            'langues',
            'disponibilite_collaboration',
            'images',
            'created_at',
            'updated_at',
        )
    
    def resolve_images(self, info):
        """Resolve images for the company"""
        return self.images.all()
    
    def resolve_address(self, info):
        """Resolve address for the company"""
        return self.address

    def resolve_disponibilite_collaboration(self, info):
        """Normalize availability value"""
        from ..influencer_node import normalize_enum_value
        return normalize_enum_value(self.disponibilite_collaboration)
