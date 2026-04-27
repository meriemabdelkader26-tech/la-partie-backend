"""GraphQL middleware utilities for request normalization."""


class NormalizeAuthorizationHeaderMiddleware:
    """Accept both Bearer and JWT authorization prefixes.

    django-graphql-jwt expects the "JWT <token>" format by default.
    Many frontend upload clients send "Bearer <token>", which causes
    authenticated mutations to fail with 401. This middleware rewrites
    Bearer to JWT before authentication middleware runs.
    """

    def resolve(self, next, root, info, **kwargs):
        request = getattr(info, "context", None)

        if request is not None and hasattr(request, "META"):
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if isinstance(auth_header, str) and auth_header.startswith("Bearer "):
                request.META["HTTP_AUTHORIZATION"] = "JWT " + auth_header[len("Bearer "):]
                print(f"[DEBUG] Normalized Bearer to JWT. New header: {request.META['HTTP_AUTHORIZATION'][:20]}...")
            elif isinstance(auth_header, str) and auth_header.startswith("JWT "):
                print(f"[DEBUG] Found JWT header: {auth_header[:20]}...")
            else:
                print(f"[DEBUG] No recognized auth header: {auth_header[:20]}...")

        return next(root, info, **kwargs)
