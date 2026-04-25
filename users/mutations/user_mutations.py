import graphene
from .chatbot_mutations import AskChatbot
from .ai_mutations import RefineCompanyDescriptionMutation
from .subscription_mutations import (
    CreateBillingPortalSession,
    CreatePlatformSubscriptionCheckoutSession,
)
from .user_mutations_all import (
    RegisterUser,
    VerifyEmailWithToken,
    VerifyEmailWithCode,
    ResendVerificationEmail,
    UpdateUser,
    VerifyEmail,
    VerifyPhone,
    AdminVerifyUser,
    BanUser,
    UnbanUser,
    DeleteUser
)


class UserMutations(graphene.ObjectType):
    """All user mutations in one place"""
    
    register_user = RegisterUser.Field()
    verify_email_with_token = VerifyEmailWithToken.Field()
    verify_email_with_code = VerifyEmailWithCode.Field()
    resend_verification_email = ResendVerificationEmail.Field()
    update_user = UpdateUser.Field()
    verify_email = VerifyEmail.Field()
    verify_phone = VerifyPhone.Field()
    admin_verify_user = AdminVerifyUser.Field()
    ban_user = BanUser.Field()
    unban_user = UnbanUser.Field()
    delete_user = DeleteUser.Field()
    create_platform_subscription_checkout_session = CreatePlatformSubscriptionCheckoutSession.Field()
    create_billing_portal_session = CreateBillingPortalSession.Field()
    refine_company_description = RefineCompanyDescriptionMutation.Field()
