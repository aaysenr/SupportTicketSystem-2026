import json
import nh3
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import ChatGroup, ChatMessage, Ticket, TicketComment, Notification


ALLOWED_TAGS = {
    'p', 'b', 'i', 'u', 'em', 'strong', 'a', 'br', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code', 'blockquote',
    'span', 'strike', 's', 'sub', 'sup'
}
ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title', 'target', 'rel'},
    'span': {'style', 'class'},
    'p': {'style', 'class'},
    'code': {'class'},
}


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
            action_type = data.get("type", "message")

            # 1. Kullanıcı Yazıyor... (Typing Indicator)
            if action_type == "typing":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_typing_broadcast",
                        "sender_id": self.user.id,
                        "sender_name": self.user.get_full_name() or self.user.username,
                        "is_typing": bool(data.get("is_typing", True))
                    }
                )
                return

            # 2. Normal Mesaj Gönderimi
            content = data.get("content", "").strip()
            if not content:
                return

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
        except Exception:
            await self.send(text_data=json.dumps({
                "status": "error",
                "message": "Mesaj işlenirken hata oluştu."
            }))

    async def chat_message_broadcast(self, event):
        """Grup kanalından gelen mesajı istemciye ilet"""
        await self.send(text_data=json.dumps({
            "status": "success",
            "type": "message",
            "message_id": event.get("message_id"),
            "sender_id": event.get("sender_id"),
            "sender_name": event.get("sender_name"),
            "content": event.get("content"),
            "created_at": event.get("created_at"),
        }))

    async def chat_typing_broadcast(self, event):
        """Kullanıcının yazdığı bilgisini diğer üyelere ilet"""
        if event.get("sender_id") != self.user.id:
            await self.send(text_data=json.dumps({
                "status": "typing",
                "type": "typing",
                "sender_id": event.get("sender_id"),
                "sender_name": event.get("sender_name"),
                "is_typing": event.get("is_typing"),
            }))

    @database_sync_to_async
    def verify_and_get_room(self):
        """Kullanıcının bu odaya erişim yetkisi var mı kontrol et ve oda adını üret"""
        try:
            if self.chat_type == "dm":
                recipient = User.objects.filter(id=self.chat_id, is_staff=True).first()
                if not recipient:
                    return False, None
                u1, u2 = sorted([self.user.id, recipient.id])
                return True, f"chat_dm_{u1}_{u2}"

            elif self.chat_type == "group":
                group = ChatGroup.objects.filter(id=self.chat_id).first()
                if not group:
                    return False, None
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
            # XSS Temizliği
            clean_content = nh3.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
            if self.chat_type == "dm":
                recipient = User.objects.get(id=self.chat_id, is_staff=True)
                msg = ChatMessage.objects.create(
                    sender=self.user,
                    recipient=recipient,
                    content=clean_content
                )
            else:
                group = ChatGroup.objects.get(id=self.chat_id)
                msg = ChatMessage.objects.create(
                    sender=self.user,
                    group=group,
                    content=clean_content
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


class TicketCommentConsumer(AsyncWebsocketConsumer):
    """
    Canlı Destek Talebi İçi Mesajlaşma (Live Ticket Chat)
    Talebe ait odaya katılan talep sahibi ve destek personelinin
    sayfayı yenilemeden anlık olarak mesajlaşmasını,
    karşı tarafın yazdığını görmesini sağlar.
    """

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4003)
            return

        self.ticket_id = int(self.scope["url_route"]["kwargs"].get("ticket_id", 0))

        # Kullanıcının bu talebe erişim hakkı olup olmadığını kontrol et
        can_access = await self.check_ticket_access()
        if not can_access:
            await self.close(code=4003)
            return

        self.room_group_name = f"ticket_{self.ticket_id}"

        # Gruba katıl
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
        """Canlı mesaj veya yazıyor... sinyali işle"""
        try:
            data = json.loads(text_data)
            action_type = data.get("type", "comment")

            # 1. Yazıyor Göstergesi
            if action_type == "typing":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "ticket_typing_broadcast",
                        "sender_id": self.user.id,
                        "sender_name": self.user.get_full_name() or self.user.username,
                        "is_staff": self.user.is_staff,
                        "is_typing": bool(data.get("is_typing", True))
                    }
                )
                return

            # 2. Canlı Yorum Gönderimi
            raw_content = data.get("content", "").strip()
            if not raw_content:
                return

            is_internal = bool(data.get("is_internal", False)) and self.user.is_staff

            comment_dict = await self.save_ticket_comment(raw_content, is_internal)
            if not comment_dict:
                return

            # Odaya yayınla
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "ticket_comment_broadcast",
                    **comment_dict
                }
            )

        except Exception:
            await self.send(text_data=json.dumps({
                "status": "error",
                "message": "İşlem sırasında hata oluştu."
            }))

    async def ticket_typing_broadcast(self, event):
        """Karşı taraf yazıyorsa göstergeyi ilet"""
        if event.get("sender_id") != self.user.id:
            await self.send(text_data=json.dumps({
                "status": "typing",
                "type": "typing",
                "sender_id": event.get("sender_id"),
                "sender_name": event.get("sender_name"),
                "is_staff": event.get("is_staff"),
                "is_typing": event.get("is_typing"),
            }))

    async def ticket_comment_broadcast(self, event):
        """Yeni yorum geldiğinde istemciye ilet (Özel notları sadece personele göster)"""
        if event.get("is_internal") and not self.user.is_staff:
            return  # Gizli personel notunu müşteriye sızdırma

        await self.send(text_data=json.dumps({
            "status": "success",
            "type": "comment",
            **event
        }))

    @database_sync_to_async
    def check_ticket_access(self):
        """Kullanıcının bu talebe erişim yetkisini doğrular"""
        try:
            ticket = Ticket.objects.select_related('created_by', 'category', 'assigned_to').get(id=self.ticket_id)
            if self.user.is_superuser:
                return True
            if ticket.created_by == self.user or ticket.assigned_to == self.user:
                return True
            if ticket.is_public:
                return True
            if self.user.is_staff:
                profile = getattr(self.user, 'profile', None)
                if not profile:
                    return True
                return profile.can_access_category(ticket.category)
            return False
        except Ticket.DoesNotExist:
            return False

    @database_sync_to_async
    def save_ticket_comment(self, raw_content, is_internal):
        """Gelen canlı yorumu veritabanına kaydeder ve bildirimleri tetikler"""
        try:
            ticket = Ticket.objects.select_related('created_by', 'category', 'assigned_to').get(id=self.ticket_id)

            clean_content = nh3.clean(raw_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
            comment = TicketComment.objects.create(
                ticket=ticket,
                author=self.user,
                content=clean_content,
                is_internal=is_internal
            )

            # SLA ilk yanıt süresi
            profile = getattr(self.user, 'profile', None)
            is_staff_commenter = self.user.is_staff or (profile and profile.is_staff_agent)
            if is_staff_commenter and not ticket.first_response_at:
                ticket.first_response_at = timezone.now()
                ticket.save(update_fields=['first_response_at'])

            # Bildirimler (Dahili not değilse müşteriye ve personele bildir)
            if not is_internal:
                from .views import send_notification_email

                # 1. Talep sahibine bildirim
                if comment.author != ticket.created_by:
                    Notification.objects.create(
                        recipient=ticket.created_by,
                        actor=comment.author,
                        ticket=ticket,
                        message=f"#{ticket.ticket_number} talebinize {comment.author.username} tarafından canlı yanıt eklendi."
                    )
                    if ticket.created_by.email:
                        send_notification_email(
                            subject=f"[Destek Talebi] #{ticket.ticket_number} Talebinize Yeni Yanıt Geldi",
                            message=f"Merhaba {ticket.created_by.username},\n\n#{ticket.ticket_number} numaralı talebinize yeni bir yanıt geldi:\n\n\"{comment.content}\"",
                            recipient_list=[ticket.created_by.email]
                        )

                # 2. Atanmış personele bildirim
                if ticket.assigned_to and comment.author != ticket.assigned_to:
                    Notification.objects.create(
                        recipient=ticket.assigned_to,
                        actor=comment.author,
                        ticket=ticket,
                        message=f"Sorumlu olduğunuz #{ticket.ticket_number} talebine canlı yanıt eklendi."
                    )
                    if ticket.assigned_to.email:
                        send_notification_email(
                            subject=f"[Destek Talebi] #{ticket.ticket_number} Talebine Canlı Yanıt Geldi",
                            message=f"Merhaba {ticket.assigned_to.username},\n\nSorumlu olduğunuz #{ticket.ticket_number} talebine {comment.author.username} tarafından yanıt yazıldı.",
                            recipient_list=[ticket.assigned_to.email]
                        )

            return {
                "comment_id": comment.id,
                "author_id": self.user.id,
                "author_name": self.user.get_full_name() or self.user.username,
                "is_staff": self.user.is_staff,
                "is_internal": comment.is_internal,
                "content": comment.content,
                "attachment_url": "",
                "attachment_name": "",
                "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M")
            }
        except Exception:
            return None
