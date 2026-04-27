from django_filters import FilterSet, OrderingFilter, CharFilter, NumberFilter, DateFilter, DateTimeFilter
from django.db.models import Q
from ..models import Offer


class OfferFilter(FilterSet):
    """Filters for searching and filtering offers in GraphQL queries"""
    
    search = CharFilter(method='filter_search', label='Search title or objective')

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | 
            Q(objectif__icontains=value) |
            Q(requirement__icontains=value)
        )

    class Meta:
        model = Offer
        fields = {
            'title': ['exact', 'icontains', 'istartswith'],
            'min_budget': ['exact', 'gte', 'lte'],
            'max_budget': ['exact', 'gte', 'lte'],
            'start_date': ['exact', 'gte', 'lte'],
            'end_date': ['exact', 'gte', 'lte'],
            'influencer_number': ['exact', 'gte', 'lte'],
            'requirement': ['exact', 'icontains'],
            'objectif': ['exact', 'icontains'],
            'created_at': ['exact', 'gte', 'lte'],
            'created_by': ['exact'],
        }
        
    ordering = OrderingFilter(
        fields=(
            ('title', 'title'),
            ('min_budget', 'min_budget'),
            ('max_budget', 'max_budget'),
            ('start_date', 'start_date'),
            ('end_date', 'end_date'),
            ('influencer_number', 'influencer_number'),
            ('created_at', 'created_at'),
        )
    )
