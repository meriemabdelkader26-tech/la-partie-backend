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

        return next(root, info, **kwargs)
