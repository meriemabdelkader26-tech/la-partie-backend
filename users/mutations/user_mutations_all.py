"""
Consolidated User Mutations
All user-related operations including registration, verification, updates, and admin actions
"""
import graphene
from graphql import GraphQLError
from graphql_relay import from_global_id
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from ..user_node import UserNode, UserRoleEnum
from ..utils import (
    generate_verification_token, 
    send_verification_email, 
    verify_email_token, 
    verify_email_code,
    safe_create_notification
)
from users.models import NotificationType

User = get_user_model()


class RegisterUser(graphene.Mutation):
    """Register a new user"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    verification_code = graphene.String()
    
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        name = graphene.String(required=True)
        phone_number = graphene.String()
        role = graphene.Argument(UserRoleEnum, required=True)
    
    def mutate(self, info, email, password, name, role, phone_number=None):
        email = (email or '').strip().lower()
        verification_required = getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', False)

        # Check if user already exists
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if existing_user.email_verified:
                raise GraphQLError('User with this email already exists')

            if not verification_required:
                existing_user.verify_email()
                return RegisterUser(
                    user=existing_user,
                    success=True,
                    message='Account already existed and is now automatically verified.',
                    verification_code=None
                )

            # Idempotent register flow for non-verified users.
            verify_token = generate_verification_token(existing_user)
            print("[DEBUG] Appel send_verification_email pour EXISTING:", existing_user.email, verify_token.code)
            email_sent = send_verification_email(existing_user, verify_token.token, verify_token.code)

            if not email_sent:
                raise GraphQLError(
                    'Registration exists but verification email could not be sent. Please retry in a moment.'
                )

            return RegisterUser(
                user=existing_user,
                success=True,
                message='Account already exists but is not verified. A new verification code was sent.',
                verification_code=verify_token.code  # Toujours retourner le code
            )
        
        # Validate password
        if len(password) < 8:
            raise GraphQLError('Password must be at least 8 characters long')
        
        # Ensure role is a string value, not an Enum object
        role_value = role.value if hasattr(role, 'value') else str(role)
        if 'EnumMeta.' in role_value:
            role_value = role_value.split('.')[-1]
            
        # Create user (email_verified will be False by default)
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            role=role_value,
            phone_number=phone_number
        )

        # Notify admins about the new user registration
        admin_users = User.objects.filter(role='ADMIN') | User.objects.filter(is_staff=True)
        for admin in admin_users.distinct():
            safe_create_notification(
                user=admin,
                notification_type=NotificationType.SYSTEM,
                title="New User Registered",
                message=f"A new {role_value.lower()} ({name}) has registered.",
                link=f"/admin/user"
            )

        if not verification_required:
            user.verify_email()
            return RegisterUser(
                user=user,
                success=True,
                message='User registered successfully. Email verification is currently disabled.',
                verification_code=None
            )
        
        # Generate verification token
        verify_token = generate_verification_token(user)
        
        # Send verification email with both token and code
        print("[DEBUG] Appel send_verification_email pour NEW:", user.email, verify_token.code)
        email_sent = send_verification_email(user, verify_token.token, verify_token.code)
        
        if not email_sent:
            # If email fails, we still return success but inform the user
            return RegisterUser(
                user=user,
                success=True,
                message='User registered successfully but verification email could not be sent. Please contact support.'
            )
        
        return RegisterUser(
            user=user,
            success=True,
            message='User registered successfully! Please check your email to verify your account.',
            verification_code=verify_token.code  # Toujours retourner le code
        )


class VerifyEmailWithToken(graphene.Mutation):
    """Verify user email using token from email link"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        token = graphene.String(required=True)
        email = graphene.String(required=True)
    
    def mutate(self, info, token, email):
        if not getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', False):
            normalized_email = (email or '').strip().lower()
            user = User.objects.filter(email=normalized_email).first()
            if not user:
                raise GraphQLError('User not found.')
            if not user.email_verified:
                user.verify_email()
            return VerifyEmailWithToken(
                user=user,
                success=True,
                message='Email verification is disabled. Account is already verified.'
            )

        # Verify the token
        success, message, user = verify_email_token(token, email)
        
        if not success:
            raise GraphQLError(message)
        
        return VerifyEmailWithToken(
            user=user,
            success=True,
            message=message
        )


class VerifyEmailWithCode(graphene.Mutation):
    """Verify user email using 6-digit code"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        code = graphene.String(required=True)
        email = graphene.String(required=True)
    
    def mutate(self, info, code, email):
        if not getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', False):
            normalized_email = (email or '').strip().lower()
            user = User.objects.filter(email=normalized_email).first()
            if not user:
                raise GraphQLError('User not found.')
            if not user.email_verified:
                user.verify_email()
            return VerifyEmailWithCode(
                user=user,
                success=True,
                message='Email verification is disabled. Account is already verified.'
            )

        # Validate code format
        if not code.isdigit() or len(code) != 6:
            raise GraphQLError('Verification code must be exactly 6 digits.')
        
        # Verify the code
        success, message, user = verify_email_code(code, email)
        
        if not success:
            raise GraphQLError(message)
        
        return VerifyEmailWithCode(
            user=user,
            success=True,
            message=message
        )


class ResendVerificationEmail(graphene.Mutation):
    """Resend verification email to user"""
    success = graphene.Boolean()
    message = graphene.String()
    verification_code = graphene.String()
    
    class Arguments:
        email = graphene.String(required=True)
    
    def mutate(self, info, email):
        if not getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', False):
            return ResendVerificationEmail(
                success=False,
                message='Email verification is disabled. No verification code is required.',
                verification_code=None
            )

        try:
            email = (email or '').strip().lower()
            user = User.objects.get(email=email)
            
            # Check if already verified
            if user.email_verified:
                return ResendVerificationEmail(
                    success=False,
                    message='Email is already verified.'
                )
            
            latest_token = user.verify_tokens.order_by('-created_at').first()
            if latest_token and latest_token.created_at >= timezone.now() - timedelta(seconds=60):
                return ResendVerificationEmail(
                    success=False,
                    message='Please wait 60 seconds before requesting a new code.',
                    verification_code=latest_token.code  # Toujours retourner le code
                )

            # Generate new verification token
            verify_token = generate_verification_token(user)
            
            # Send verification email with both token and code
            email_sent = send_verification_email(user, verify_token.token, verify_token.code)
            
            if not email_sent:
                raise GraphQLError('Failed to send verification email. Please try again later.')
            
            return ResendVerificationEmail(
                success=True,
                message='Verification email sent successfully! Please check your inbox.',
                verification_code=verify_token.code  # Toujours retourner le code
            )
            
        except User.DoesNotExist:
            # Don't reveal if email exists for security
            return ResendVerificationEmail(
                success=True,
                message='If the email exists, a verification link has been sent.',
                verification_code=None
            )


class UpdateUser(graphene.Mutation):
    """Update user information"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        user_id = graphene.ID(required=True)
        name = graphene.String()
        phone_number = graphene.String()
        email_verified = graphene.Boolean()
        phone_number_verified = graphene.Boolean()
        is_verify_by_admin = graphene.Boolean()
        is_banned = graphene.Boolean()
        role = graphene.Argument(UserRoleEnum)
    
    def mutate(self, info, user_id, **kwargs):
        current_user = info.context.user
        
        if not current_user.is_authenticated:
            raise GraphQLError('Authentication required')
        
        # Decode global ID
        try:
            print(f"DEBUG: UPDATE_USER raw user_id = {user_id}")
            node_type, pk = from_global_id(user_id)
            print(f"DEBUG: from_global_id -> type: {node_type}, pk: {pk}")
            if node_type == 'UserNode':
                user_id = pk
            print(f"DEBUG: final user_id = {user_id}")
        except Exception as e:
            print(f"DEBUG: from_global_id exception: {e}")
            pass # Use user_id as is if it's not a valid global ID

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        # Only allow users to update their own profile or admins to update any
        if user.id != current_user.id and not current_user.is_staff:
            raise GraphQLError('Permission denied')
        
        # Update fields
        if 'name' in kwargs:
            user.name = kwargs['name']
        if 'phone_number' in kwargs:
            user.phone_number = kwargs['phone_number']
        
        # Admin-only fields
        if current_user.is_staff:
            if 'email_verified' in kwargs:
                user.email_verified = kwargs['email_verified']
            if 'phone_number_verified' in kwargs:
                user.phone_number_verified = kwargs['phone_number_verified']
            if 'is_verify_by_admin' in kwargs:
                user.is_verify_by_admin = kwargs['is_verify_by_admin']
            if 'is_banned' in kwargs:
                if kwargs['is_banned']:
                    user.ban_user()
                else:
                    user.unban_user()
            if 'role' in kwargs:
                role_val = kwargs['role']
                role_val = role_val.value if hasattr(role_val, 'value') else str(role_val)
                if 'EnumMeta.' in role_val:
                    role_val = role_val.split('.')[-1]
                user.role = role_val
        
        user.save()
        
        return UpdateUser(
            user=user,
            success=True,
            message='User updated successfully'
        )


class VerifyEmail(graphene.Mutation):
    """Verify user email"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        user_id = graphene.ID(required=True)
    
    def mutate(self, info, user_id):
        current_user = info.context.user
        
        if not current_user.is_authenticated:
            raise GraphQLError('Authentication required')
        
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        # Only allow users to verify their own email or admins
        if user.id != current_user.id and not current_user.is_staff:
            raise GraphQLError('Permission denied')
        
        user.verify_email()
        
        return VerifyEmail(
            user=user,
            success=True,
            message='Email verified successfully'
        )


class VerifyPhone(graphene.Mutation):
    """Verify user phone number"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        user_id = graphene.ID(required=True)
    
    def mutate(self, info, user_id):
        current_user = info.context.user
        
        if not current_user.is_authenticated:
            raise GraphQLError('Authentication required')
        
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        # Only allow users to verify their own phone or admins
        if user.id != current_user.id and not current_user.is_staff:
            raise GraphQLError('Permission denied')
        
        user.verify_phone()
        
        return VerifyPhone(
            user=user,
            success=True,
            message='Phone number verified successfully'
        )


class AdminVerifyUser(graphene.Mutation):
    """Admin verify a user"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        user_id = graphene.ID(required=True)
    
    def mutate(self, info, user_id):
        current_user = info.context.user
        
        if not current_user.is_authenticated or not current_user.is_staff:
            raise GraphQLError('Admin permission required')
        
        # Decode global ID
        try:
            node_type, pk = from_global_id(user_id)
            if node_type != 'UserNode':
                raise GraphQLError('Invalid user ID')
        except Exception:
            raise GraphQLError('Invalid user ID format')
        
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        user.admin_verify()
        
        return AdminVerifyUser(
            user=user,
            success=True,
            message='User verified by admin successfully'
        )


class BanUser(graphene.Mutation):
    """Ban a user"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        user_id = graphene.ID(required=True)
    
    def mutate(self, info, user_id):
        current_user = info.context.user
        
        if not current_user.is_authenticated or not current_user.is_staff:
            raise GraphQLError('Admin permission required')
        
        # Decode global ID
        try:
            node_type, pk = from_global_id(user_id)
            if node_type != 'UserNode':
                raise GraphQLError('Invalid user ID')
        except Exception:
            raise GraphQLError('Invalid user ID format')
        
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        user.ban_user()
        
        return BanUser(
            user=user,
            success=True,
            message='User banned successfully'
        )


class UnbanUser(graphene.Mutation):
    """Unban a user"""
    user = graphene.Field(UserNode)
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        user_id = graphene.ID(required=True)
    
    def mutate(self, info, user_id):
        current_user = info.context.user
        
        if not current_user.is_authenticated or not current_user.is_staff:
            raise GraphQLError('Admin permission required')
        
        # Decode global ID
        try:
            node_type, pk = from_global_id(user_id)
            if node_type != 'UserNode':
                raise GraphQLError('Invalid user ID')
        except Exception:
            raise GraphQLError('Invalid user ID format')
        
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        user.unban_user()
        
        return UnbanUser(
            user=user,
            success=True,
            message='User unbanned successfully'
        )


class DeleteUser(graphene.Mutation):
    """Delete a user"""
    success = graphene.Boolean()
    message = graphene.String()
    
    class Arguments:
        user_id = graphene.ID(required=True)
    
    def mutate(self, info, user_id):
        current_user = info.context.user
        
        if not current_user.is_authenticated:
            raise GraphQLError('Authentication required')
        
        # Decode global ID
        try:
            node_type, pk = from_global_id(user_id)
            if node_type != 'UserNode':
                raise GraphQLError('Invalid user ID')
        except Exception:
            raise GraphQLError('Invalid user ID format')
        
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise GraphQLError('User not found')
        
        # Only allow users to delete their own account or admins to delete any
        if user.id != current_user.id and not current_user.is_staff:
            raise GraphQLError('Permission denied')
        
        user.delete()
        
        return DeleteUser(
            success=True,
            message='User deleted successfully'
        )
