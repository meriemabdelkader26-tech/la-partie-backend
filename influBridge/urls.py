from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from graphene_file_upload.django import FileUploadGraphQLView
from django.views.decorators.csrf import csrf_exempt
from schema_graph.views import Schema
from django.shortcuts import render
from .schema import schema
from offer.payment_webhooks import stripe_webhook

admin.site.site_header = "InfluBridge Admin"
admin.site.site_title = "InfluBridge Admin Portal"
admin.site.index_title = "Welcome to InfluBridge Admin Portal"

def home(request):
    """Home page with API information"""
    import django
    return render(request, 'home.html', {
        'django_version': django.get_version(),
    })

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path("schema/", Schema.as_view()),
    path('graphql', csrf_exempt(FileUploadGraphQLView.as_view(graphiql=True, schema=schema))),
    path('graphql/', csrf_exempt(FileUploadGraphQLView.as_view(graphiql=True, schema=schema))),
    path('api/payments/stripe/webhook/', stripe_webhook, name='stripe-webhook'),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)