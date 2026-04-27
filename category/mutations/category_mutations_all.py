"""
Consolidated Category Mutations
All CRUD operations for Category model with admin permission requirements
"""
from graphene_django_cud.mutations import (
    DjangoCreateMutation,
    DjangoUpdateMutation,
    DjangoPatchMutation,
    DjangoDeleteMutation,
    DjangoBatchCreateMutation,
    DjangoBatchDeleteMutation
)
from ..models import Category
from graphql import GraphQLError
from graphql_jwt.decorators import login_required


class CategoryCreateMutation(DjangoCreateMutation):
    """Create a new category"""
    
    class Meta:
        model = Category
        exclude = ['created', 'modified']
    
    @classmethod
    @login_required
    def check_permissions(cls, root, info, input):
        """Only allow admin users to create categories"""
        user = info.context.user
        user_email = getattr(user, 'email', 'Anonymous')
        print(f"[DEBUG] CategoryCreateMutation check_permissions for user: {user_email}")
        print(f"[DEBUG] user.is_staff: {getattr(user, 'is_staff', False)}, user.is_admin: {getattr(user, 'is_admin', False)}, user.role: {getattr(user, 'role', 'N/A')}")
        
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
            print(f"[DEBUG] Permission DENIED for user: {user_email}")
            raise GraphQLError("Admin privileges required")
        
        print(f"[DEBUG] Permission GRANTED for user: {user_email}")
        return True


class CategoryUpdateMutation(DjangoUpdateMutation):
    """Update an existing category"""
    
    class Meta:
        model = Category
        exclude = ['created', 'modified']
    
    @classmethod
    @login_required
    def check_permissions(cls, root, info, input, id, obj):
        """Only allow admin users to update categories"""
        user = info.context.user
        user_email = getattr(user, 'email', 'Anonymous')
        print(f"[DEBUG] CategoryUpdateMutation check_permissions for user: {user_email}")
        print(f"[DEBUG] user.is_staff: {getattr(user, 'is_staff', False)}, user.is_admin: {getattr(user, 'is_admin', False)}, user.role: {getattr(user, 'role', 'N/A')}")
        
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
            print(f"[DEBUG] Permission DENIED for user: {user_email}")
            raise GraphQLError("Admin privileges required")
        
        print(f"[DEBUG] Permission GRANTED for user: {user_email}")
        return True


class CategoryPatchMutation(DjangoPatchMutation):
    """Partially update a category (only specific fields)"""
    
    class Meta:
        model = Category
        exclude = ['created', 'modified']
    
    @classmethod
    @login_required
    def check_permissions(cls, root, info, input, id, obj):
        """Only allow admin users to patch categories"""
        user = info.context.user
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
            raise GraphQLError("Admin privileges required")
        return True


class CategoryDeleteMutation(DjangoDeleteMutation):
    """Delete a single category"""
    
    class Meta:
        model = Category
    
    @classmethod
    @login_required
    def check_permissions(cls, root, info, input, id):
        """Only allow admin users to delete categories"""
        user = info.context.user
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
            raise GraphQLError("Admin privileges required")
        return True


class CategoryBatchCreateMutation(DjangoBatchCreateMutation):
    """Create multiple categories at once"""
    
    class Meta:
        model = Category
        exclude = ['created', 'modified']
    
    @classmethod
    @login_required
    def check_permissions(cls, root, info, input):
        """Only allow admin users to batch create categories"""
        user = info.context.user
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
            raise GraphQLError("Admin privileges required")
        return True


class CategoryBatchDeleteMutation(DjangoBatchDeleteMutation):
    """Delete multiple categories at once"""
    
    class Meta:
        model = Category
    
    @classmethod
    @login_required
    def check_permissions(cls, root, info, input):
        """Only allow admin users to batch delete categories"""
        user = info.context.user
        if not (getattr(user, 'is_staff', False) or getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
            raise GraphQLError("Admin privileges required")
        return True
