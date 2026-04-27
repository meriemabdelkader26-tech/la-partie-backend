import graphene
from .auth_mutations_all import (
    ObtainJSONWebToken,
    VerifyToken,
    RefreshToken,
    RevokeToken,
    ChangePassword,
    ForgotPassword,
    ResetPassword,
    ResetPasswordRequest,
    LogoutMutation
)


class AuthMutations(graphene.ObjectType):
    """All authentication mutations in one place"""
    
    # JWT token operations
    token_auth = ObtainJSONWebToken.Field()
    verify_token = VerifyToken.Field()
    refresh_token = RefreshToken.Field()
    revoke_token = RevokeToken.Field()
    logout = LogoutMutation.Field()
    
    # Password management
    change_password = ChangePassword.Field()
    forgot_password = ForgotPassword.Field()
    reset_password = ResetPassword.Field()
    reset_password_request = ResetPasswordRequest.Field() 

