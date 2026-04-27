import graphene
from ..user_node import UserNode
from graphene_django.filter import DjangoFilterConnectionField
from ..filters import UserFilter
from ..models import User


class UserListQuery(graphene.ObjectType):
    """
    Query to get all users with pagination and totalCount.
    
    Supports filtering and ordering through UserFilter.
    Available ordering fields: email, name, created_at, updated_at, is_active, role
    Use ordering parameter with field name (e.g., "name") or prepend with "-" for descending (e.g., "-created_at")
    """

    all_users = DjangoFilterConnectionField(
        UserNode,
        filterset_class=UserFilter
    )
    
    def resolve_all_users(self, info, **kwargs):
        """
        Get all users with pagination (admin only).
        
        Supports ordering via 'ordering' parameter:
        - email, -email
        - name, -name
        - created_at, -created_at (default: -created_at)
        - updated_at, -updated_at
        - is_active, -is_active
        - role, -role
        """
        user = info.context.user
        if not user.is_authenticated or not (user.is_staff or user.is_admin or user.is_superuser):
            return User.objects.none()
        
        # Exclude staff users by default
        return User.objects.filter(is_staff=False)
