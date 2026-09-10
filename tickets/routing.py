from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/team-chat/(?P<chat_type>group|dm)/(?P<chat_id>\d+)/$", consumers.TeamChatConsumer.as_asgi()),
]
