"""
Consolidated Authentication Mutations
All authentication-related operations including JWT, password management, etc.
"""
import graphene
import graphql_jwt
from graphql_jwt.decorators import login_required
from graphql import GraphQLError
from django.contrib.auth import get_user_model, authenticate
from django.conf import settings
from ..user_node import UserNode
from ..utils import (
    generate_password_reset_token,
    send_password_reset_email,
    verify_password_reset_token,
    verify_password_reset_code
)

User = get_user_model()


class ObtainJSONWebToken(graphql_jwt.JSONWebTokenMutation):
    """Custom JWT token obtain mutation with user details and verification checks"""
    user = graphene.Field(UserNode)
    
    @classmethod
    def mutate(cls, root, info, **kwargs):
        # Get email and password from kwargs
        email = kwargs.get('email') or kwargs.get(User.USERNAME_FIELD)
        password = kwargs.get('password')
        
        if not email or not password:
            raise GraphQLError('Please provide both email and password')
        
        # Authenticate user
        user = authenticate(request=info.context, username=email, password=password)
        
        if user is None:
            raise GraphQLError('Invalid email or password')
        
        # IMPORTANT: Refresh user from database to get the latest role and data
        # This ensures the JWT token contains the current role, not cached data
        user.refresh_from_db()
        
        # Debug logging
        print(f"[AUTH] Login attempt for: {user.email}")
        print(f"[AUTH] Current role from DB: '{user.role}'")
        
        # Check if user is banned
        if user.is_banned:
            raise GraphQLError('Your account has been banned. Please contact support.')
        
        # Check if user is active
        if not user.is_active:
            raise GraphQLError('Your account is inactive. Please contact support.')
        
        # Check if email is verified
        if getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', False) and not user.email_verified:
            raise GraphQLError('Please verify your email address before logging in.')
        
        # Check if profile is completed
        if user.is_completed_profile:
            # If profile is complete, check admin verification
            # Exclude ADMINs from this check
            if not user.is_verify_by_admin and user.role != 'ADMIN' and not user.is_superuser:
                raise GraphQLError('Your profile is complete but still pending admin verification. Please wait for approval.')
        
        # If all checks pass, call the parent mutate method
        return super().mutate(root, info, **kwargs)
    
    @classmethod
    def resolve(cls, root, info, **kwargs):
        return cls(user=info.context.user)


class VerifyToken(graphql_jwt.Verify):
    """Verify JWT token"""
    pass


class RefreshToken(graphql_jwt.Refresh):
    """Refresh JWT token"""
    pass


class RevokeToken(graphql_jwt.Revoke):
    """Revoke JWT token"""
    pass


class ChangePassword(graphene.Mutation):
    """Change user password"""
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        old_password = graphene.String(required=True)
        new_password = graphene.String(required=True)
    
    @login_required
    def mutate(self, info, old_password, new_password):
        user = info.context.user
        
        # Check if old password is correct
        if not user.check_password(old_password):
            raise GraphQLError('Old password is incorrect')
        
        # Validate new password
        if len(new_password) < 8:
            raise GraphQLError('New password must be at least 8 characters long')
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        return ChangePassword(
            success=True,
            message='Password changed successfully'
        )


class ForgotPassword(graphene.Mutation):
    """Request password reset - generates and sends reset token via email"""
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        email = graphene.String(required=True)
    
    def mutate(self, info, email):
        try:
            user = User.objects.get(email=email)
            
            # Generate password reset token
            reset_token = generate_password_reset_token(user)
            
            # Send password reset email
            email_sent = send_password_reset_email(
                user=user,
                token=reset_token.token,
                code=reset_token.code
            )
            
            if email_sent:
                return ForgotPassword(
                    success=True,
                    message='Password reset instructions have been sent to your email'
                )
            else:
                return ForgotPassword(
                    success=False,
                    message='Failed to send password reset email. Please try again later.'
                )
                
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return ForgotPassword(
                success=True,
                message='If the email exists, password reset instructions have been sent'
            )


class ResetPassword(graphene.Mutation):
    """Reset password using token or code"""
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        email = graphene.String(required=True)
        new_password = graphene.String(required=True)
        token = graphene.String(required=False)
        code = graphene.String(required=False)
    
    def mutate(self, info, email, new_password, token=None, code=None):
        # Validate that either token or code is provided
        if not token and not code:
            raise GraphQLError('Either token or code must be provided')
        
        # Validate new password
        if len(new_password) < 8:
            raise GraphQLError('New password must be at least 8 characters long')
        
        # Verify token or code
        if token:
            success, message, reset_token = verify_password_reset_token(token, email)
        else:
            success, message, reset_token = verify_password_reset_code(code, email)
        
        if not success:
            raise GraphQLError(message)
        
        # Get the user
        user = reset_token.user
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Mark token as used
        reset_token.mark_as_used()
        
        return ResetPassword(
            success=True,
            message='Password has been reset successfully. You can now log in with your new password.'
        )


class ResetPasswordRequest(graphene.Mutation):
    """Request password reset (placeholder for email sending)"""
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        email = graphene.String(required=True)
    
    def mutate(self, info, email):
        try:
            user = User.objects.get(email=email)
            # TODO: Implement email sending logic with reset token
            # For now, just return success
            return ResetPasswordRequest(
                success=True,
                message='Password reset instructions sent to your email'
            )
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return ResetPasswordRequest(
                success=True,
                message='If the email exists, password reset instructions have been sent'
            )
