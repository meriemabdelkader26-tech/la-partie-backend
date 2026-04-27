from django_filters import FilterSet, OrderingFilter, CharFilter, BooleanFilter, DateTimeFilter
from django.db.models import Q
from ..models import User


class UserFilter(FilterSet):
    """Filters for searching and filtering users in GraphQL queries"""
    
    search = CharFilter(method='filter_search', label='Search name or email')

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | 
            Q(email__icontains=value) |
            Q(phone_number__icontains=value)
        )

    class Meta:
        model = User
        fields = {
            'email': ['exact', 'icontains', 'istartswith'],
            'name': ['exact', 'icontains', 'istartswith'],
            'phone_number': ['exact', 'icontains'],
            'role': ['exact'],
            'email_verified': ['exact'],
            'phone_number_verified': ['exact'],
            'is_verify_by_admin': ['exact'],
            'is_banned': ['exact'],
            'is_active': ['exact'],
            'is_staff': ['exact'],
            'is_completed_profile': ['exact'],
            'created_at': ['exact', 'gte', 'lte'],
            'updated_at': ['exact', 'gte', 'lte'],
        }
        
    ordering = OrderingFilter(
        fields=(
            ('email', 'email'),
            ('name', 'name'),
            ('role', 'role'),
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('email_verified', 'email_verified'),
            ('is_active', 'is_active'),
            ('is_banned', 'is_banned'),
        )
    )
