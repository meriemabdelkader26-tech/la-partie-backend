import graphene
from graphene_django.filter import DjangoFilterConnectionField
from ..user_node import UserNode, UserConnection
from ..models import User
from ..filters import UserFilter
from common.pagination_utils import OffsetConnectionField


class UserQueries(graphene.ObjectType):
    """GraphQL queries for User"""
    user = graphene.relay.Node.Field(UserNode)
    
    # Use DjangoFilterConnectionField with UserFilter for advanced filtering
    all_users = DjangoFilterConnectionField(
        UserNode,
        filterset_class=UserFilter
    )
    
    me = graphene.Field(UserNode)
    
    def resolve_all_users(self, info, **kwargs):
        """Get all users with pagination (admin only)"""
        user = info.context.user
        if not user.is_authenticated or not (user.is_staff or user.is_admin or user.is_superuser):
            return User.objects.none()
        
        # Exclude staff users by default unless explicitly requested
        qs = User.objects.all()
        
        # If is_staff filter is not provided, exclude staff by default
        if 'is_staff' not in kwargs:
            qs = qs.filter(is_staff=False)
        
        return qs
    
    def resolve_me(self, info):
        """Get current authenticated user"""
        user = info.context.user
        if user.is_authenticated:
            return user
        return None
