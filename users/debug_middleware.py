class DebugUserMiddleware:
    def resolve(self, next, root, info, **kwargs):
        user = getattr(info.context, 'user', None)
        if user and user.is_authenticated:
            print(f"[DEBUG] Request User: {user.email}, is_authenticated: {user.is_authenticated}, is_staff: {user.is_staff}, role: {getattr(user, 'role', 'N/A')}")
        elif user:
            print(f"[DEBUG] Request User: Anonymous, is_authenticated: False")
        else:
            print("[DEBUG] Request User: None")
        return next(root, info, **kwargs)
