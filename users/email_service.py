"""Email service with logging and fallback support"""
import os
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """Centralized email service with logging and fallback"""
    
    @staticmethod
    def send_verification_email(user, token, code):
        """
        Send verification email with comprehensive error handling
        
        Args:
            user: User instance
            token: Verification token
            code: 6-digit verification code
            
        Returns:
            Tuple (success: bool, message: str)
        """
        print(">>> ENVOI EMAIL VERIF à", user.email, "avec code", code)
        try:
            # Generate verification link
            verification_link = f"{settings.FRONTEND_URL}/verify-email/{token}?email={user.email}"
            
            # Render HTML email
            html_message = render_to_string('emails/verify_email.html', {
                'user_name': user.name,
                'verification_link': verification_link,
                'verification_code': code,
            })
            
            # Create plain text version
            plain_message = strip_tags(html_message)
            
            # Log attempt
            logger.info(f"[EMAIL] Attempting to send verification email to {user.email}")
            logger.info(f"[EMAIL] Email Host: {settings.EMAIL_HOST}")
            logger.info(f"[EMAIL] Email Port: {settings.EMAIL_PORT}")
            logger.info(f"[EMAIL] From: {settings.DEFAULT_FROM_EMAIL}")
            
            # Try to send email
            result = send_mail(
                subject='Verify Your Email - InfluBridge',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,  # Let exceptions bubble up
            )
            
            logger.info(f"[SUCCESS] Email sent successfully to {user.email}")
            return True, "Email sent successfully"
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[ERROR] Error sending verification email to {user.email}: {error_msg}")
            logger.error(f"[ERROR] Exception type: {type(e).__name__}")
            
            # Log the full traceback for debugging
            import traceback
            logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # In development mode, save email to console backend
            if settings.DEBUG and os.getenv('DEBUG_EMAIL', 'False') == 'True':
                logger.warning(f"[WARNING] DEBUG MODE: Email would have been sent to {user.email}")
                logger.warning(f"[WARNING] Code: {code}")
                return True, "Email logged to console (DEBUG mode)"
            
            return False, f"Failed to send email: {error_msg}"
    
    @staticmethod
    def send_password_reset_email(user, token, code):
        """
        Send password reset email
        
        Args:
            user: User instance
            token: Reset token
            code: 6-digit code
            
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{token}?email={user.email}"
            
            html_message = render_to_string('emails/reset_password.html', {
                'user_name': user.name,
                'reset_link': reset_link,
                'reset_code': code,
            })
            
            plain_message = strip_tags(html_message)
            
            logger.info(f"[EMAIL] Sending password reset email to {user.email}")
            
            send_mail(
                subject='Reset Your Password - InfluBridge',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"[SUCCESS] Password reset email sent to {user.email}")
            return True, "Email sent successfully"
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[ERROR] Error sending password reset email: {error_msg}")
            
            if settings.DEBUG and os.getenv('DEBUG_EMAIL', 'False') == 'True':
                print(f"[DEBUG] Tentative d'envoi d'email de vérification à {user.email} avec code {code}")
                return True, "Email logged to console (DEBUG mode)"
            
            return False, f"Failed to send email: {error_msg}"


def diagnose_email_config():
    """Diagnose email configuration issues"""
    print("\n" + "="*60)
    print("[DIAGNOSTIC] EMAIL CONFIGURATION DIAGNOSTIC REPORT")
    print("="*60)
    
    print(f"v EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"v EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"v EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"v EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"v EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"v DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"v DEBUG: {settings.DEBUG}")
    print(f"v DEBUG_EMAIL: {os.getenv('DEBUG_EMAIL', 'Not set')}")
    
    # Test connection
    print("\n[TEST] Testing SMTP Connection...")
    try:
        from django.core.mail import get_connection
        connection = get_connection()
        connection.open()
        connection.close()
        print("[SUCCESS] SMTP connection successful!")
    except Exception as e:
        print(f"[ERROR] SMTP connection failed: {e}")
    
    print("="*60 + "\n")
