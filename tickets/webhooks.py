import json
import logging
import threading
import urllib.request
import urllib.error
from django.conf import settings

logger = logging.getLogger(__name__)


def _send_webhook_request(url, payload):
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'SupportTicketSystem-Webhook/1.0'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            status_code = response.getcode()
            logger.info("[WEBHOOK] Harici webhook başarıyla iletildi (HTTP %s): %s", status_code, url)
    except urllib.error.HTTPError as err:
        logger.error("[WEBHOOK] Webhook HTTP hatası (%s): %s", err.code, err.read().decode('utf-8', errors='ignore'))
    except Exception as exc:
        logger.error("[WEBHOOK] Webhook gönderim hatası: %s", exc)


def send_outgoing_webhook(ticket, event_type="urgent_ticket_created"):
    """
    Acil durumlar (Urgent) ve SLA ihlalleri için Slack, Discord veya Teams kanallarına
    arka planda asenkron webhook kartı gönderir.
    """
    webhook_url = getattr(settings, 'OUTGOING_WEBHOOK_URL', '')
    if not webhook_url:
        return

    # Olay Başlığı & Rengi
    if event_type == "sla_breached":
        title = f"⚠️ [SLA İHLALİ] #{ticket.ticket_number} - {ticket.title}"
        color_dec = 0xE74C3C  # Kırmızı
        status_text = "SLA Hedef Süresi Aşıldı!"
    elif event_type == "urgent_ticket_updated":
        title = f"🔥 [ACİL TALEP GÜNCELLENDİ] #{ticket.ticket_number} - {ticket.title}"
        color_dec = 0xE67E22  # Turuncu
        status_text = f"Durum: {ticket.get_status_display()}"
    else:
        title = f"🚨 [YENİ ACİL TALEP] #{ticket.ticket_number} - {ticket.title}"
        color_dec = 0xC0392B  # Koyu Kırmızı
        status_text = f"Öncelik: {ticket.get_priority_display()} | Durum: {ticket.get_status_display()}"

    category_name = ticket.category.name if ticket.category else "Genel"
    creator_name = ticket.created_by.get_full_name() or ticket.created_by.username
    assigned_name = ticket.assigned_to.username if ticket.assigned_to else "Atanmadı"

    # Discord Uyumlu Embed Formatı
    if "discord.com" in webhook_url:
        payload = {
            "content": f"**{title}**",
            "embeds": [
                {
                    "title": f"#{ticket.ticket_number} - {ticket.title}",
                    "description": ticket.description[:300] + ("..." if len(ticket.description) > 300 else ""),
                    "color": color_dec,
                    "fields": [
                        {"name": "Kategori", "value": category_name, "inline": True},
                        {"name": "Öncelik", "value": ticket.get_priority_display(), "inline": True},
                        {"name": "Durum", "value": ticket.get_status_display(), "inline": True},
                        {"name": "Oluşturan", "value": creator_name, "inline": True},
                        {"name": "Atanan", "value": assigned_name, "inline": True},
                        {"name": "Bilgi", "value": status_text, "inline": True},
                    ],
                    "footer": {"text": "Destek Yönetim Sistemi - Canlı Bildirim"}
                }
            ]
        }
    else:
        # Slack / Teams / Standart Block Kit Formatı
        payload = {
            "text": f"{title}\nKategori: {category_name} | Atanan: {assigned_name} | {status_text}\nAçıklama: {ticket.description[:200]}"
        }

    thread = threading.Thread(
        target=_send_webhook_request,
        args=(webhook_url, payload),
        daemon=True
    )
    thread.start()
