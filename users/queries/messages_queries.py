import graphene
from django.db.models import Q
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from graphql_relay import from_global_id

from ..models import Conversation, Message, Notification
from ..message_node import ConversationNode, MessageNode, NotificationNode


class MessagesQueries(graphene.ObjectType):
    """Queries for user-to-user messaging."""

    my_conversations = graphene.List(ConversationNode)
    conversation_messages = graphene.List(
        MessageNode,
        conversation_id=graphene.ID(required=True),
    )
    my_notifications = graphene.List(
        NotificationNode,
        first=graphene.Int(required=False),
    )

    @login_required
    def resolve_my_conversations(self, info):
        user = info.context.user
        conversations = (
            Conversation.objects.filter(Q(company=user) | Q(influencer=user))
            .select_related('company', 'influencer')
            .prefetch_related('messages__sender')
            .order_by('-updated_at')
        )
        return conversations

    @login_required
    def resolve_conversation_messages(self, info, conversation_id):
        user = info.context.user

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

        Message.objects.filter(conversation=conversation, is_read=False).exclude(sender=user).update(is_read=True)

        return conversation.messages.select_related('sender').all()

    @login_required
    def resolve_my_notifications(self, info, first=None):
        user = info.context.user
        queryset = Notification.objects.filter(user=user).order_by('-created_at')
        if first and first > 0:
            return list(queryset[:first])
        return queryset
