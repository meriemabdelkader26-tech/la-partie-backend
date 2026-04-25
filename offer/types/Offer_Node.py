import graphene
from graphene_django import DjangoObjectType
from graphene import relay
from ..models import Offer


class OfferConnection(relay.Connection):
    """Connection for Offer with totalCount and offset pagination support"""
    
    total_count = graphene.Int()
    
    class Meta:
        abstract = True
    
    def resolve_total_count(root, info, **kwargs):
        """Resolve total count from stored length or iterable"""
        return root.length if hasattr(root, 'length') else (
            root.iterable.count() if hasattr(root, 'iterable') and hasattr(root.iterable, 'count') else len(root.edges)
        )


class OfferNode(DjangoObjectType):
    """GraphQL Node for Offer - defines what data can be queried"""
    
    applications_count = graphene.Int()
    pending_applications_count = graphene.Int()
    approved_applications_count = graphene.Int()
    is_applied = graphene.Boolean()
    application_status = graphene.String()
    is_saved = graphene.Boolean()

    class Meta:
        model = Offer
        interfaces = (relay.Node,)
        connection_class = OfferConnection
    
    @classmethod
    def get_queryset(cls, queryset, info):
        """Optimize queryset to reduce database hits"""
        return queryset.select_related('created_by').prefetch_related('applications', 'applications__user')
    
    def resolve_applications_count(self, info):
        """Get total count of applications"""
        return self.applications.count()
    
    def resolve_pending_applications_count(self, info):
        """Get count of pending applications"""
        return self.applications.filter(status='Pending').count()
    
    def resolve_approved_applications_count(self, info):
        """Get count of approved applications"""
        return self.applications.filter(status='Approved').count()

    def resolve_is_applied(self, info):
        """Check if the current user has applied to this offer"""
        user = info.context.user
        if not user.is_authenticated:
            return False
        return self.applications.filter(user=user).exists()

    def resolve_application_status(self, info):
        """Get the status of the current user's application to this offer"""
        user = info.context.user
        if not user.is_authenticated:
            return None
        application = self.applications.filter(user=user).first()
        return application.status if application else None

    def resolve_is_saved(self, info):
        """Check if the current user has saved this offer"""
        user = info.context.user
        if not user.is_authenticated:
            return False
        return self.saved_by_users.filter(user=user).exists()
