import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import ChatGroup, ChatMessage


class TeamChatConsumer(AsyncWebsocketConsumer):
    """
    Ekip Sohbeti WebSocket Tüketicisi (Real-Time Team Chat)
    Desteklenen Kanallar:
      - Grup Odaları (Genel Ekip Odası, Özel Gruplar): chat_type='group', chat_id=<group_id>
      - Birebir Mesajlaşma (DM): chat_type='dm', chat_id=<recipient_user_id>
    """

    async def connect(self):
        self.user = self.scope.get("user")

        # Güvenlik Kontrolü: Giriş yapmış ve yetkili personel olmalı
        if not self.user or not self.user.is_authenticated or not self.user.is_staff:
            await self.close(code=4003)
            return

        self.chat_type = self.scope["url_route"]["kwargs"].get("chat_type")
        self.chat_id = int(self.scope["url_route"]["kwargs"].get("chat_id", 0))

        # Kanal Yetki ve Oda Adı Doğrulaması
        is_authorized, room_name = await self.verify_and_get_room()
        if not is_authorized:
            await self.close(code=4003)
            return

        self.room_group_name = room_name

        # Odaya katıl
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """İstemciden gelen WebSocket mesajını işle ve gruba dağıt"""
        try:
            data = json.loads(text_data)
            content = data.get("content", "").strip()
            if not content:
                return

            # Veritabanına kaydet
            msg_data = await self.save_message(content)
            if not msg_data:
                return

            # Gruba yayınla (Broadcast)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message_broadcast",
                    **msg_data
                }
            )
        except Exception as e:
            # Hata durumunda istemciye bildir
            await self.send(text_data=json.dumps({
                "status": "error",
                "message": "Mesaj işlenirken hata oluştu."
            }))

    async def chat_message_broadcast(self, event):
        """Grup kanalından gelen mesajı istemciye ilet"""
        await self.send(text_data=json.dumps({
            "status": "success",
            "message_id": event.get("message_id"),
            "sender_id": event.get("sender_id"),
            "sender_name": event.get("sender_name"),
            "content": event.get("content"),
            "created_at": event.get("created_at"),
        }))

    @database_sync_to_async
    def verify_and_get_room(self):
        """Kullanıcının bu odaya erişim yetkisi var mı kontrol et ve oda adını üret"""
        try:
            if self.chat_type == "dm":
                recipient = User.objects.filter(id=self.chat_id, is_staff=True).first()
                if not recipient:
                    return False, None
                # Simetrik oda adı (Kullanıcı ID'leri sıralı)
                u1, u2 = sorted([self.user.id, recipient.id])
                return True, f"chat_dm_{u1}_{u2}"

            elif self.chat_type == "group":
                group = ChatGroup.objects.filter(id=self.chat_id).first()
                if not group:
                    return False, None
                # Grup üyesi veya süper yönetici olmalı
                if group.is_general or self.user.is_superuser or group.members.filter(id=self.user.id).exists():
                    return True, f"chat_group_{group.id}"
                return False, None

            return False, None
        except Exception:
            return False, None

    @database_sync_to_async
    def save_message(self, content):
        """Mesajı veritabanına kaydet ve döndür"""
        try:
            if self.chat_type == "dm":
                recipient = User.objects.get(id=self.chat_id, is_staff=True)
                msg = ChatMessage.objects.create(
                    sender=self.user,
                    recipient=recipient,
                    content=content
                )
            else:
                group = ChatGroup.objects.get(id=self.chat_id)
                msg = ChatMessage.objects.create(
                    sender=self.user,
                    group=group,
                    content=content
                )

            return {
                "message_id": msg.id,
                "sender_id": self.user.id,
                "sender_name": self.user.get_full_name() or self.user.username,
                "content": msg.content,
                "created_at": msg.created_at.strftime("%H:%M")
            }
        except Exception:
            return None
