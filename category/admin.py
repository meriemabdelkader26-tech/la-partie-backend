from django.contrib import admin
from django.utils.html import format_html
from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model"""
    
    list_display = ['name', 'description_short', 'status_badge', 'created', 'modified']
    list_filter = ['is_active', 'created', 'modified']
    search_fields = ['name', 'description']
    ordering = ['-created']
    list_per_page = 25
    
    fieldsets = [
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
    ]
    
    actions = ['make_active', 'make_inactive']
    
    def description_short(self, obj):
        """Show short description"""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Description'
    
    def status_badge(self, obj):
        """Show colored status badge"""
        if obj.is_active:
            return format_html('<span style="color: #ec4899;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    status_badge.short_description = 'Status'
    
    def make_active(self, request, queryset):
        """Mark selected categories as active"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} categories marked as active.')
    make_active.short_description = "Activate selected categories"
    
    def make_inactive(self, request, queryset):
        """Mark selected categories as inactive"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} categories marked as inactive.')
    make_inactive.short_description = "Deactivate selected categories"