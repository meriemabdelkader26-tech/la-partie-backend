import requests
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
import mimetypes

@require_GET
def proxy_image(request):
    """
    Proxy an external image to bypass CORS and Referer restrictions.
    """
    url = request.GET.get('url')
    if not url:
        return HttpResponseNotFound("URL parameter is required")
        
    try:
        # Request the image without a Referer header
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type')
            if not content_type:
                content_type, _ = mimetypes.guess_type(url)
                if not content_type:
                    content_type = 'image/jpeg' # Fallback
                    
            # Return the image data
            django_response = HttpResponse(response.content, content_type=content_type)
            # Allow caching to reduce load on our proxy
            django_response['Cache-Control'] = 'public, max-age=86400'
            # Add CORS headers
            django_response['Access-Control-Allow-Origin'] = '*' 
            django_response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            django_response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept'
            
            return django_response
            
        return HttpResponseNotFound(f"Image fetch failed with status {response.status_code}")
        
    except Exception as e:
        return HttpResponseNotFound(f"Error fetching image: {str(e)}")
