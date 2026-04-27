from django_filters import FilterSet, OrderingFilter, CharFilter, BooleanFilter, DateTimeFilter
from django.db.models import Q
from ..models import Category


class CategoryFilter(FilterSet):
    """Filters for searching and filtering categories in GraphQL queries"""
    
    search = CharFilter(method='filter_search', label='Search name or description')

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | 
            Q(description__icontains=value)
        )

    class Meta:
        model = Category
        fields = {
            'name': ['exact', 'icontains', 'istartswith'],
            'description': ['exact', 'icontains'],
            'is_active': ['exact'],
            'created': ['exact', 'gte', 'lte'],
            'modified': ['exact', 'gte', 'lte'],
        }
        
    ordering = OrderingFilter(
        fields=(
            ('name', 'name'),
            ('created', 'created'),
            ('modified', 'modified'),
            ('is_active', 'is_active'),
        )
    )
