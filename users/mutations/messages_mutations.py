import graphene
from django.contrib.auth import get_user_model
from django.db.utils import OperationalError, ProgrammingError
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from graphql_relay import from_global_id

from ..message_node import ConversationNode, MessageNode
from ..models import Conversation, Message, Notification, NotificationType
from ..utils import normalize_role

User = get_user_model()


class SendMessage(graphene.Mutation):
    """Send a message to an existing or new conversation."""

    ok = graphene.Boolean()
    error = graphene.String()
    conversation = graphene.Field(ConversationNode)
    message = graphene.Field(MessageNode)

    class Arguments:
        content = graphene.String(required=True)
        conversation_id = graphene.ID(required=False)
        receiver_id = graphene.ID(required=False)

    @login_required
    def mutate(self, info, content, conversation_id=None, receiver_id=None):
        user = info.context.user
        content = (content or '').strip()

        if not content:
            raise GraphQLError('Message content is required')

        conversation = None

        if conversation_id:
            try:
                node_type, pk = from_global_id(conversation_id)
                if node_type and node_type != 'ConversationNode':
                    raise GraphQLError('Invalid conversation id')
                lookup_id = pk
            except Exception:
                lookup_id = conversation_id

            try:
                conversation = Conversation.objects.get(pk=lookup_id)
            except Conversation.DoesNotExist:
                raise GraphQLError('Conversation not found')

            if user.id not in (conversation.company_id, conversation.influencer_id):
                raise GraphQLError('You do not have access to this conversation')

        else:
            if not receiver_id:
                raise GraphQLError('receiverId is required when conversationId is not provided')

            try:
                node_type, pk = from_global_id(receiver_id)
                if node_type and node_type != 'UserNode':
                    raise GraphQLError('Invalid receiver id')
                receiver_lookup = pk
            except Exception:
                receiver_lookup = receiver_id

            try:
                receiver = User.objects.get(pk=receiver_lookup)
            except User.DoesNotExist:
                raise GraphQLError('Receiver not found')

            if user.id == receiver.id:
                raise GraphQLError('Cannot send a message to yourself')

            user_role = (normalize_role(user.role) or '').upper()
            receiver_role = (normalize_role(receiver.role) or '').upper()

            if user_role == 'COMPANY' and receiver_role == 'INFLUENCER':
                company_user = user
                influencer_user = receiver
            elif user_role == 'INFLUENCER' and receiver_role == 'COMPANY':
                company_user = receiver
                influencer_user = user
            elif user_role == 'ADMIN':
                if receiver_role == 'COMPANY':
                    company_user = receiver
                    influencer_user = user
                else: # ADMIN messaging INFLUENCER or other ADMIN
                    company_user = user
                    influencer_user = receiver
            elif receiver_role == 'ADMIN':
                if user_role == 'COMPANY':
                    company_user = user
                    influencer_user = receiver
                else: # INFLUENCER or other ADMIN messaging ADMIN
                    company_user = receiver
                    influencer_user = user
            else:
                raise GraphQLError('Messages are only allowed between company and influencer accounts')

            conversation, _ = Conversation.objects.get_or_create(
                company=company_user,
                influencer=influencer_user,
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=user,
            content=content,
        )

        # Notify the recipient with a persistent in-app notification.
        recipient = conversation.influencer if user.id == conversation.company_id else conversation.company
        recipient_role = (normalize_role(recipient.role) or '').upper()
        
        if recipient_role == 'INFLUENCER':
            messages_path = '/influencer/messages'
        elif recipient_role == 'COMPANY':
            messages_path = '/company/messages'
        else:
            messages_path = '/admin/chat'
            
        try:
            Notification.objects.create(
                user=recipient,
                notification_type=NotificationType.MESSAGE,
                title=f"New message from {user.name or user.email}",
                message=content[:180],
                link=f"{messages_path}?conversationId={conversation.id}",
                is_read=False,
            )
        except (OperationalError, ProgrammingError):
            # Keep message delivery functional even if notifications migration is pending.
            pass

        conversation.save(update_fields=['updated_at'])

        return SendMessage(ok=True, error=None, conversation=conversation, message=message)


class MarkAllNotificationsRead(graphene.Mutation):
    """Mark all notifications as read for the current user."""

    ok = graphene.Boolean()
    updated_count = graphene.Int()

    @login_required
    def mutate(self, info):
        user = info.context.user
        try:
            updated = Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        except (OperationalError, ProgrammingError):
            updated = 0
        return MarkAllNotificationsRead(ok=True, updated_count=updated)


class MessagesMutations(graphene.ObjectType):
    """Messaging mutations."""

    send_message = SendMessage.Field()
    mark_all_notifications_read = MarkAllNotificationsRead.Field()
