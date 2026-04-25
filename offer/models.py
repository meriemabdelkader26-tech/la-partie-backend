from django.db import models
from django.conf import settings



class ApplicationStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'
    WITHDRAW = 'Withdraw', 'Withdraw'


class PaymentStatus(models.TextChoices):
    UNPAID = 'Unpaid', 'Unpaid'
    IN_ESCROW = 'InEscrow', 'In Escrow'
    RELEASED = 'Released', 'Released'
    REFUNDED = 'Refunded', 'Refunded'


class PayoutRequestStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'
    PAID = 'Paid', 'Paid'


class PaymentMethodType(models.TextChoices):
    PAYPAL = 'PayPal', 'PayPal'
    BANK_TRANSFER = 'BankTransfer', 'Bank Transfer'
    STRIPE = 'Stripe', 'Stripe'



class Offer(models.Model):
    title = models.CharField(max_length=200)
    min_budget = models.DecimalField(max_digits=10, decimal_places=2)
    max_budget = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    influencer_number = models.PositiveIntegerField()
    requirement = models.TextField()
    objectif = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_offers'
    )

    def __str__(self):
        return self.title



class OfferApplication(models.Model):
    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    proposal = models.TextField()
    asking_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional professional fields
    cover_letter = models.TextField(blank=True, null=True, help_text="Optional cover letter from influencer")
    estimated_reach = models.PositiveIntegerField(null=True, blank=True, help_text="Estimated audience reach")
    delivery_days = models.PositiveIntegerField(null=True, blank=True, help_text="Estimated days to complete")
    portfolio_links = models.JSONField(default=list, blank=True, help_text="Links to previous work")
    rejection_reason = models.TextField(blank=True, null=True, help_text="Reason for rejection (if applicable)")
    admin_notes = models.TextField(blank=True, null=True, help_text="Internal notes for admin")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications',
        help_text="Admin who reviewed the application"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, help_text="When the application was reviewed")

    # Payment lifecycle fields (MVP escrow flow)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID
    )
    payment_reference = models.CharField(max_length=120, blank=True, null=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('offer', 'user')
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['offer', 'status']),
        ]

    def __str__(self):
        user_display = getattr(self.user, 'name', None) or getattr(self.user, 'email', f'User {self.user.id}')
        return f"{user_display} - {self.offer.title} ({self.status})"
    
    @property
    def is_pending(self):
        return self.status == ApplicationStatus.PENDING
    
    @property
    def is_approved(self):
        return self.status == ApplicationStatus.APPROVED
    
    @property
    def is_rejected(self):
        return self.status == ApplicationStatus.REJECTED


class SavedOffer(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_offers'
    )
    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        related_name='saved_by_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'offer_savedoffer'
        unique_together = ('user', 'offer')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} saved {self.offer.title}"


class InfluencerPaymentMethod(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    method_type = models.CharField(
        max_length=30,
        choices=PaymentMethodType.choices,
        default=PaymentMethodType.PAYPAL,
    )
    label = models.CharField(max_length=100)
    details = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_primary']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.label} ({self.method_type})"


class PayoutRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payout_requests'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=PayoutRequestStatus.choices,
        default=PayoutRequestStatus.PENDING,
    )
    payment_method = models.ForeignKey(
        InfluencerPaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payout_requests'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['-requested_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - ${self.amount} ({self.status})"
