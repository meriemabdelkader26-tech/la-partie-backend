from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from enum import Enum


class UserRole(Enum):
    ADMIN = "ADMIN"
    COMPANY = "COMPANY"
    INFLUENCER = "INFLUENCER"

    @classmethod
    def choices(cls):
        return [(role.value, role.name.capitalize()) for role in cls]


class SubscriptionPlan(models.TextChoices):
    FREE = 'FREE', 'Free'
    PLUS = 'PLUS', 'Plus'
    PRO = 'PRO', 'Pro'


class SubscriptionStatus(models.TextChoices):
    INACTIVE = 'INACTIVE', 'Inactive'
    ACTIVE = 'ACTIVE', 'Active'
    TRIALING = 'TRIALING', 'Trialing'
    PAST_DUE = 'PAST_DUE', 'Past due'
    CANCELED = 'CANCELED', 'Canceled'
    UNPAID = 'UNPAID', 'Unpaid'
    INCOMPLETE = 'INCOMPLETE', 'Incomplete'


class CustomUserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verify_by_admin', True)
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('role', UserRole.ADMIN.value)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email as username and role-based access"""

    email = models.EmailField(unique=True, max_length=255, db_index=True)
    name = models.CharField(max_length=255)

    phone_number = models.CharField(max_length=20, blank=True, null=True)
    phone_number_verified = models.BooleanField(default=False)

    email_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)
    is_verify_by_admin = models.BooleanField(default=False)

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices(),
        default=UserRole.INFLUENCER.value
    )

    is_banned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_completed_profile = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.email})"

    def verify_email(self):
        self.email_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=['email_verified', 'verified_at'])

    def verify_phone(self):
        self.phone_number_verified = True
        self.save(update_fields=['phone_number_verified'])

    def ban_user(self):
        self.is_banned = True
        self.is_active = False
        self.save(update_fields=['is_banned', 'is_active'])

    def unban_user(self):
        self.is_banned = False
        self.is_active = True
        self.save(update_fields=['is_banned', 'is_active'])

    def admin_verify(self):
        self.is_verify_by_admin = True
        self.save(update_fields=['is_verify_by_admin'])

    @property
    def is_admin(self):
        if not self.role:
            return False
        role_str = str(self.role)
        normalized_role = role_str.split('.')[-1] if '.' in role_str else role_str
        return normalized_role == UserRole.ADMIN.value

    @property
    def is_company(self):
        if not self.role:
            return False
        role_str = str(self.role)
        normalized_role = role_str.split('.')[-1] if '.' in role_str else role_str
        return normalized_role == UserRole.COMPANY.value

    @property
    def is_influencer(self):
        if not self.role:
            return False
        role_str = str(self.role)
        normalized_role = role_str.split('.')[-1] if '.' in role_str else role_str
        return normalized_role == UserRole.INFLUENCER.value


class UserSubscription(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='subscription',
    )
    plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.FREE,
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.INACTIVE,
    )
    stripe_customer_id = models.CharField(max_length=120, blank=True, null=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True, null=True, db_index=True)
    stripe_price_id = models.CharField(max_length=120, blank=True, null=True)
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_subscriptions'
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
        indexes = [
            models.Index(fields=['plan', 'status']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.plan} ({self.status})"


class VerifyToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verify_tokens')
    token = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=6, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'verify_tokens'
        verbose_name = 'Verify Token'
        verbose_name_plural = 'Verify Tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f"Token for {self.user.email} - Code: {self.code} - Used: {self.is_used}"

    def mark_as_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=255, unique=True, db_index=True)
    code = models.CharField(max_length=6, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f"Password Reset for {self.user.email} - Code: {self.code} - Used: {self.is_used}"

    def mark_as_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])


class Conversation(models.Model):
    """Direct conversation between one company and one influencer."""

    company = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='company_conversations',
    )
    influencer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='influencer_conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        ordering = ['-updated_at']
        unique_together = ['company', 'influencer']

    def __str__(self):
        return f"Conversation {self.company.email} <-> {self.influencer.email}"


class Message(models.Model):
    """Message exchanged in a conversation."""

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.sender.email} at {self.created_at.isoformat()}"


class NotificationType(models.TextChoices):
    MESSAGE = 'message', 'Message'
    APPLICATION = 'application', 'Application'
    PAYOUT = 'payout', 'Payout'
    SYSTEM = 'system', 'System'


class Notification(models.Model):
    """Persistent in-app notification for a user."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
    )
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True, default='')
    link = models.CharField(max_length=500, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"
