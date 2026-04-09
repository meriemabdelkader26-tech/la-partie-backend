import graphene
from graphene_django import DjangoObjectType

from .models import Conversation, Message, Notification
from .user_node import UserNode


class MessageNode(DjangoObjectType):
    """GraphQL node for chat message."""

    class Meta:
        model = Message
        fields = ('id', 'conversation', 'sender', 'content', 'is_read', 'created_at')
        interfaces = (graphene.relay.Node,)


class ConversationNode(DjangoObjectType):
    """GraphQL node for company-influencer conversation."""

    last_message = graphene.Field(MessageNode)
    unread_count = graphene.Int()
    other_participant = graphene.Field(UserNode)
    messages = graphene.List(MessageNode)

    class Meta:
        model = Conversation
        fields = ('id', 'company', 'influencer', 'created_at', 'updated_at')
        interfaces = (graphene.relay.Node,)

    def resolve_last_message(self, info):
        return self.messages.order_by('-created_at').select_related('sender').first()

    def resolve_unread_count(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return 0
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    def resolve_other_participant(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return None
        return self.influencer if user.id == self.company_id else self.company

    def resolve_messages(self, info):
        return self.messages.select_related('sender').all()


class NotificationNode(DjangoObjectType):
    """GraphQL node for user notifications."""

    class Meta:
        model = Notification
        fields = (
            'id',
            'notification_type',
            'title',
            'message',
            'link',
            'is_read',
            'created_at',
        )
        interfaces = (graphene.relay.Node,)
