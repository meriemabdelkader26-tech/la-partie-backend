from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from offer.models import Offer, OfferApplication
from users.models import (
    SubscriptionPlan,
    SubscriptionStatus,
    UserRole,
    UserSubscription,
)
from users.utils import normalize_role


ACTIVE_SUBSCRIPTION_STATUSES = {
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.PAST_DUE,
}


@dataclass
class QuotaSnapshot:
    role: str
    plan: str
    subscription_status: str
    period_start: timezone.datetime
    period_end: timezone.datetime
    campaigns_used: int
    campaigns_limit: Optional[int]
    campaigns_remaining: Optional[int]
    applications_used: int
    applications_limit: Optional[int]
    applications_remaining: Optional[int]
    can_create_campaign: bool
    can_apply_to_campaign: bool
    has_active_paid_plan: bool
    campaign_block_message: Optional[str]
    application_block_message: Optional[str]


def _int_setting(name: str, default: int) -> int:
    value = getattr(settings, name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _limit_or_none(value: int) -> Optional[int]:
    # A value <= 0 means unlimited.
    return None if value <= 0 else value


def get_or_create_user_subscription(user):
    subscription, _ = UserSubscription.objects.get_or_create(user=user)
    return subscription


def has_paid_access(subscription: UserSubscription, now=None) -> bool:
    if not subscription:
        return False

    now = now or timezone.now()

    if subscription.plan == SubscriptionPlan.FREE:
        return False

    if subscription.status not in ACTIVE_SUBSCRIPTION_STATUSES:
        return False

    if subscription.current_period_end and subscription.current_period_end <= now:
        return False

    return True


def _month_window(now):
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _week_window(now):
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end


def _plan_limits_for_role(role: str, plan: str):
    if role == UserRole.COMPANY.value:
        limits = {
            SubscriptionPlan.FREE: _limit_or_none(_int_setting('COMPANY_FREE_CAMPAIGNS_PER_MONTH', 3)),
            SubscriptionPlan.PLUS: _limit_or_none(_int_setting('COMPANY_PLUS_CAMPAIGNS_PER_MONTH', 30)),
            SubscriptionPlan.PRO: _limit_or_none(_int_setting('COMPANY_PRO_CAMPAIGNS_PER_MONTH', 0)),
        }
        return {
            'campaigns_limit': limits.get(plan),
            'applications_limit': None,
        }

    if role == UserRole.INFLUENCER.value:
        limits = {
            SubscriptionPlan.FREE: _limit_or_none(_int_setting('INFLUENCER_FREE_APPLICATIONS_PER_WEEK', 5)),
            SubscriptionPlan.PLUS: _limit_or_none(_int_setting('INFLUENCER_PLUS_APPLICATIONS_PER_WEEK', 40)),
            SubscriptionPlan.PRO: _limit_or_none(_int_setting('INFLUENCER_PRO_APPLICATIONS_PER_WEEK', 0)),
        }
        return {
            'campaigns_limit': None,
            'applications_limit': limits.get(plan),
        }

    return {
        'campaigns_limit': None,
        'applications_limit': None,
    }


def _remaining(limit_value: Optional[int], used: int) -> Optional[int]:
    if limit_value is None:
        return None
    return max(limit_value - used, 0)


def get_user_quota_snapshot(user) -> QuotaSnapshot:
    now = timezone.now()
    role = normalize_role(getattr(user, 'role', '')) or ''

    month_start, month_end = _month_window(now)
    week_start, week_end = _week_window(now)

    campaigns_used = Offer.objects.filter(
        created_by=user,
        created_at__gte=month_start,
        created_at__lt=month_end,
    ).count()

    applications_used = OfferApplication.objects.filter(
        user=user,
        submitted_at__gte=week_start,
        submitted_at__lt=week_end,
    ).count()

    if role not in {UserRole.COMPANY.value, UserRole.INFLUENCER.value}:
        return QuotaSnapshot(
            role=role,
            plan=SubscriptionPlan.PRO,
            subscription_status=SubscriptionStatus.ACTIVE,
            period_start=now,
            period_end=now + timedelta(days=1),
            campaigns_used=campaigns_used,
            campaigns_limit=None,
            campaigns_remaining=None,
            applications_used=applications_used,
            applications_limit=None,
            applications_remaining=None,
            can_create_campaign=True,
            can_apply_to_campaign=True,
            has_active_paid_plan=True,
            campaign_block_message=None,
            application_block_message=None,
        )

    subscription = get_or_create_user_subscription(user)
    has_paid_plan = has_paid_access(subscription, now=now)
    effective_plan = subscription.plan if has_paid_plan else SubscriptionPlan.FREE
    limits = _plan_limits_for_role(role, effective_plan)

    campaigns_limit = limits['campaigns_limit']
    applications_limit = limits['applications_limit']

    campaigns_remaining = _remaining(campaigns_limit, campaigns_used)
    applications_remaining = _remaining(applications_limit, applications_used)

    can_create_campaign = campaigns_remaining is None or campaigns_remaining > 0
    can_apply_to_campaign = applications_remaining is None or applications_remaining > 0

    campaign_block_message = None
    application_block_message = None

    if role == UserRole.COMPANY.value and not can_create_campaign:
        if effective_plan == SubscriptionPlan.FREE:
            campaign_block_message = (
                f"Free plan limit reached: {campaigns_used}/{campaigns_limit} campaigns this month. "
                "Upgrade to Plus or Pro to publish more campaigns."
            )
        else:
            campaign_block_message = (
                f"{effective_plan.title()} plan limit reached: {campaigns_used}/{campaigns_limit} campaigns this month. "
                "Upgrade to Pro for more capacity."
            )

    if role == UserRole.INFLUENCER.value and not can_apply_to_campaign:
        if effective_plan == SubscriptionPlan.FREE:
            application_block_message = (
                f"Free plan limit reached: {applications_used}/{applications_limit} applications this week. "
                "Upgrade to Plus or Pro to keep applying."
            )
        else:
            application_block_message = (
                f"{effective_plan.title()} plan limit reached: {applications_used}/{applications_limit} applications this week. "
                "Upgrade to Pro for higher limits."
            )

    return QuotaSnapshot(
        role=role,
        plan=effective_plan,
        subscription_status=subscription.status,
        period_start=month_start if role == UserRole.COMPANY.value else week_start,
        period_end=month_end if role == UserRole.COMPANY.value else week_end,
        campaigns_used=campaigns_used,
        campaigns_limit=campaigns_limit,
        campaigns_remaining=campaigns_remaining,
        applications_used=applications_used,
        applications_limit=applications_limit,
        applications_remaining=applications_remaining,
        can_create_campaign=can_create_campaign,
        can_apply_to_campaign=can_apply_to_campaign,
        has_active_paid_plan=has_paid_plan,
        campaign_block_message=campaign_block_message,
        application_block_message=application_block_message,
    )
