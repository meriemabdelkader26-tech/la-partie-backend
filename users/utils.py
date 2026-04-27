"""Utility functions for user management"""
import random
import uuid
from datetime import timedelta

from django.apps import apps
from django.utils import timezone
from graphql_jwt.utils import jwt_payload as default_jwt_payload

from django.db.utils import OperationalError, ProgrammingError
from .email_service import EmailService


def safe_create_notification(**kwargs):
    """
    Safely create a notification without breaking the main flow if the database 
    table is missing or locked.
    """
    Notification = apps.get_model('users', 'Notification')
    try:
        return Notification.objects.create(**kwargs)
    except (OperationalError, ProgrammingError):
        # Do not break core business flows when notification table is unavailable.
        return None


def normalize_role(role):
    """
    Normalize role value to handle corrupted data.
    Converts 'EnumMeta.INFLUENCER' -> 'INFLUENCER'
    
    Args:
        role: Role string (may be corrupted with 'EnumMeta.' prefix)
        
    Returns:
        Normalized role string
    """
    if not role:
        return role
    role_str = str(role)
    return role_str.split('.')[-1] if '.' in role_str else role_str


def check_user_role(user, expected_role):
    """
    Check if user has the expected role, handling corrupted role values.
    
    Args:
        user: User instance
        expected_role: Expected role string (e.g., 'INFLUENCER', 'COMPANY', 'ADMIN')
        
    Returns:
        Boolean indicating if user has the expected role
    """
    user_role = normalize_role(user.role)
    return user_role == expected_role


def jwt_payload_handler(user, context=None):
    """
    Custom JWT payload handler to include name, email, and role in token
    
    Args:
        user: User instance
        context: GraphQL context (optional)
        
    Returns:
        Dictionary with JWT payload
    """
    # Get default payload (includes username, exp, origIat)
    payload = default_jwt_payload(user, context)
    
    # Normalize role to handle any corrupted values
    normalized_role = normalize_role(user.role)
    
    # Debug logging
    print(f"[AUTH] Generating JWT token for: {user.email}")
    print(f"[AUTH] Role: {user.role} -> Normalized: {normalized_role}")
    
    # Add custom fields - normalize role to handle corrupted values
    payload['email'] = user.email
    payload['name'] = user.name
    payload['role'] = normalized_role
    payload['userId'] = user.id
    payload['isVerifyByAdmin'] = user.is_verify_by_admin
    payload['isCompletedProfile'] = user.is_completed_profile
    payload['isStaff'] = user.is_staff
    
    if hasattr(user, 'influencer_profile'):
        try:
            profile_pic = user.influencer_profile.images.filter(is_default=True).first()
            if not profile_pic:
                profile_pic = user.influencer_profile.images.first()
            if profile_pic:
                payload['profilePicture'] = getattr(profile_pic, 'url', None) or getattr(profile_pic, 'image', None) and getattr(profile_pic.image, 'url', None)
        except Exception as e:
            print(f"Error getting profile picture: {e}")
            
    if hasattr(user, 'company_profile') and not payload.get('profilePicture'):
        try:
            profile_pic = user.company_profile.logo
            if profile_pic:
                payload['profilePicture'] = profile_pic.url if hasattr(profile_pic, 'url') else str(profile_pic)
        except Exception as e:
            print(f"Error getting company profile picture: {e}")
    
    return payload


def generate_verification_code():
    """Generate a random 6-digit verification code"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def generate_verification_token(user):
    """
    Generate a unique verification token and code for a user
    
    Args:
        user: User instance
        
    Returns:
        VerifyToken instance
    """
    VerifyToken = apps.get_model('users', 'VerifyToken')
    
    # Mark previous unused tokens as used to keep one valid code per user.
    VerifyToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Generate unique token
    token = str(uuid.uuid4())
    
    # Generate 6-digit code
    code = generate_verification_code()
    
    # Set expiration (24 hours from now)
    expires_at = timezone.now() + timedelta(hours=24)
    
    # Create verification token
    verify_token = VerifyToken.objects.create(
        user=user,
        token=token,
        code=code,
        expires_at=expires_at
    )
    
    return verify_token


def send_verification_email(user, token, code):
    """
    Send verification email to user
    
    Args:
        user: User instance
        token: Token string
        code: 6-digit verification code
        
    Returns:
        Boolean indicating success
    """
    success, message = EmailService.send_verification_email(user, token, code)
    return success


def verify_email_token(token, email):
    """
    Verify an email token
    
    Args:
        token: Token string
        email: User email
        
    Returns:
        Tuple of (success: bool, message: str, user: User or None)
    """
    VerifyToken = apps.get_model('users', 'VerifyToken')
    email = (email or '').strip().lower()
    token = (token or '').strip()
    
    try:
        # Get the verification token
        verify_token = VerifyToken.objects.get(
            token=token,
            user__email=email
        )
        
        # Check if token is already used
        if verify_token.is_used:
            return False, "This verification link has already been used.", None
        
        # Check if token is expired
        if verify_token.expires_at < timezone.now():
            return False, "This verification link has expired. Please request a new one.", None
        
        # Get the user
        user = verify_token.user
        
        # Mark token as used
        verify_token.mark_as_used()
        
        # Verify the user's email
        user.verify_email()
        
        return True, "Email verified successfully! You can now log in.", user
        
    except VerifyToken.DoesNotExist:
        return False, "Invalid verification link.", None
    except Exception as e:
        print(f"Error verifying email token: {str(e)}")
        return False, "An error occurred while verifying your email.", None


def verify_email_code(code, email):
    """
    Verify an email using 6-digit code
    
    Args:
        code: 6-digit verification code
        email: User email
        
    Returns:
        Tuple of (success: bool, message: str, user: User or None)
    """
    VerifyToken = apps.get_model('users', 'VerifyToken')
    email = (email or '').strip().lower()
    code = (code or '').strip()
    
    try:
        # Get the verification token by code and email
        verify_token = VerifyToken.objects.filter(
            code=code,
            user__email=email,
            is_used=False
        ).order_by('-created_at').first()
        
        if not verify_token:
            return False, "Invalid verification code.", None
        
        # Check if token is expired
        if verify_token.expires_at < timezone.now():
            return False, "This verification code has expired. Please request a new one.", None
        
        # Get the user
        user = verify_token.user
        
        # Mark token as used
        verify_token.mark_as_used()
        
        # Verify the user's email
        user.verify_email()
        
        return True, "Email verified successfully! You can now log in.", user
        
    except Exception as e:
        print(f"Error verifying email code: {str(e)}")
        return False, "An error occurred while verifying your email.", None


def generate_password_reset_token(user):
    """
    Generate a unique password reset token and code for a user
    
    Args:
        user: User instance
        
    Returns:
        PasswordResetToken instance
    """
    PasswordResetToken = apps.get_model('users', 'PasswordResetToken')
    
    # Generate unique token
    token = str(uuid.uuid4())
    
    # Generate 6-digit code
    code = generate_verification_code()
    
    # Set expiration (1 hour from now)
    expires_at = timezone.now() + timedelta(hours=1)
    
    # Create password reset token
    reset_token = PasswordResetToken.objects.create(
        user=user,
        token=token,
        code=code,
        expires_at=expires_at
    )
    
    return reset_token


def send_password_reset_email(user, token, code):
    """
    Send password reset email to user
    
    Args:
        user: User instance
        token: Token string
        code: 6-digit reset code
        
    Returns:
        Boolean indicating success
    """
    success, message = EmailService.send_password_reset_email(user, token, code)
    return success


def verify_password_reset_token(token, email):
    """
    Verify a password reset token
    
    Args:
        token: Token string
        email: User email
        
    Returns:
        Tuple of (success: bool, message: str, reset_token: PasswordResetToken or None)
    """
    PasswordResetToken = apps.get_model('users', 'PasswordResetToken')
    
    try:
        # Get the password reset token
        reset_token = PasswordResetToken.objects.get(
            token=token,
            user__email=email
        )
        
        # Check if token is already used
        if reset_token.is_used:
            return False, "This password reset link has already been used.", None
        
        # Check if token is expired
        if reset_token.expires_at < timezone.now():
            return False, "This password reset link has expired. Please request a new one.", None
        
        return True, "Token is valid.", reset_token
        
    except PasswordResetToken.DoesNotExist:
        return False, "Invalid password reset link.", None
    except Exception as e:
        print(f"Error verifying password reset token: {str(e)}")
        return False, "An error occurred while verifying your password reset link.", None


def verify_password_reset_code(code, email):
    """
    Verify a password reset using 6-digit code
    
    Args:
        code: 6-digit reset code
        email: User email
        
    Returns:
        Tuple of (success: bool, message: str, reset_token: PasswordResetToken or None)
    """
    PasswordResetToken = apps.get_model('users', 'PasswordResetToken')
    
    try:
        # Get the password reset token by code and email
        reset_token = PasswordResetToken.objects.filter(
            code=code,
            user__email=email,
            is_used=False
        ).order_by('-created_at').first()
        
        if not reset_token:
            return False, "Invalid reset code.", None
        
        # Check if token is expired
        if reset_token.expires_at < timezone.now():
            return False, "This reset code has expired. Please request a new one.", None
        
        return True, "Code is valid.", reset_token
        
    except Exception as e:
        print(f"Error verifying password reset code: {str(e)}")
        return False, "An error occurred while verifying your reset code.", None
