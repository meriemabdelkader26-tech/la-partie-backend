import graphene
from graphene_django import DjangoObjectType
from .models import User, UserRole
from .billing import get_user_quota_snapshot
from common.pagination_utils import PaginatedConnection


class UserRoleEnum(graphene.Enum):
    """GraphQL Enum for User Roles"""
    ADMIN = UserRole.ADMIN.value
    COMPANY = UserRole.COMPANY.value
    INFLUENCER = UserRole.INFLUENCER.value


class UserConnection(PaginatedConnection):
    """Connection for User with totalCount and offset pagination support"""
    
    class Meta:
        abstract = True


class UserNode(DjangoObjectType):
    """GraphQL Node for User model"""
    role = graphene.Field(UserRoleEnum)
    influencer_profile = graphene.Field('users.influencer_node.InfluencerNode')
    billing_plan = graphene.String()
    billing_subscription_status = graphene.String()
    billing_period_start = graphene.DateTime()
    billing_period_end = graphene.DateTime()
    campaigns_used = graphene.Int()
    campaigns_limit = graphene.Int()
    campaigns_remaining = graphene.Int()
    applications_used = graphene.Int()
    applications_limit = graphene.Int()
    applications_remaining = graphene.Int()
    can_create_campaign = graphene.Boolean()
    can_apply_to_campaign = graphene.Boolean()
    has_active_paid_plan = graphene.Boolean()
    
    class Meta:
        model = User
        fields = (
            'id', 'email', 'name', 'phone_number', 'phone_number_verified',
            'email_verified', 'verified_at', 'is_verify_by_admin', 'role',
            'is_banned', 'is_active', 'is_staff', 'is_superuser',
            'is_completed_profile', 'created_at', 'updated_at', 'last_login'
        )
        filter_fields = {
            'email': ['exact', 'icontains'],
            'name': ['exact', 'icontains'],
            'role': ['exact'],
            'email_verified': ['exact'],
            'phone_number_verified': ['exact'],
            'is_verify_by_admin': ['exact'],
            'is_banned': ['exact'],
            'is_active': ['exact'],
            'is_staff': ['exact'],
        }
        interfaces = (graphene.relay.Node,)
        connection_class = UserConnection
    
    def resolve_role(self, info):
        """Convert Django role to GraphQL enum"""
        role = getattr(self, 'role', None)
        if role:
            # Handle incorrectly stored roles like 'EnumMeta.COMPANY'
            role_str = str(role)
            if 'EnumMeta.' in role_str:
                role_value = role_str.split('.')[-1]  # Extract 'COMPANY' from 'EnumMeta.COMPANY'
                return role_value
            return role
        return None
    
    def resolve_influencer_profile(self, info):
        """Get influencer profile if user is an influencer"""
        if not getattr(self, 'is_authenticated', False):
            return None
            
        from .utils import check_user_role
        if check_user_role(self, 'INFLUENCER'):
            try:
                return self.influencer_profile
            except:
                return None
        return None

    def _quota_snapshot(self):
        if not getattr(self, 'is_authenticated', False):
            return None
            
        if not hasattr(self, '_cached_quota_snapshot'):
            self._cached_quota_snapshot = get_user_quota_snapshot(self)
        return self._cached_quota_snapshot

    def resolve_billing_plan(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.plan if snapshot else None

    def resolve_billing_subscription_status(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.subscription_status if snapshot else None

    def resolve_billing_period_start(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.period_start if snapshot else None

    def resolve_billing_period_end(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.period_end if snapshot else None

    def resolve_campaigns_used(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.campaigns_used if snapshot else 0

    def resolve_campaigns_limit(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.campaigns_limit if snapshot else None

    def resolve_campaigns_remaining(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.campaigns_remaining if snapshot else None

    def resolve_applications_used(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.applications_used if snapshot else 0

    def resolve_applications_limit(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.applications_limit if snapshot else None

    def resolve_applications_remaining(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.applications_remaining if snapshot else None

    def resolve_can_create_campaign(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.can_create_campaign if snapshot else False

    def resolve_can_apply_to_campaign(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.can_apply_to_campaign if snapshot else False

    def resolve_has_active_paid_plan(self, info):
        snapshot = self._quota_snapshot()
        return snapshot.has_active_paid_plan if snapshot else False
