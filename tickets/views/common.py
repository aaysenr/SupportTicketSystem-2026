import os
import threading
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

def _async_email_worker(subject, message, recipient_list, html_message=None):
    try:
        from django.conf import settings
        valid_recipients = [email for email in recipient_list if email]
        if valid_recipients:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=valid_recipients,
                html_message=html_message,
                fail_silently=False
            )
            logger.info("[E-POSTA] E-posta başarıyla gönderildi: Konu='%s'", subject)
    except Exception as exc:
        logger.error("[E-POSTA] E-posta gönderiminde hata: %s", exc)




def send_notification_email(subject, message, recipient_list, ticket=None, action_url=None, html_message=None):
    """
    Güvenli, Markalı (HTML) ve Asenkron (Non-blocking) E-posta Bildirim Gönderici.
    Ana HTTP istek döngüsünü bloke etmeden arka planda zengin HTML e-posta gönderir.
    """
    if recipient_list and any(recipient_list):
        if not html_message:
            try:
                from django.template.loader import render_to_string
                html_message = render_to_string('emails/ticket_notification_email.html', {
                    'subject': subject,
                    'message': message,
                    'ticket': ticket,
                    'action_url': action_url,
                })
            except Exception as e:
                logger.warning("[E-POSTA] HTML şablonu derlenemedi, düz metin ile devam ediliyor: %s", e)
                html_message = None

        recipients = ", ".join([e for e in recipient_list if e])
        logger.info("[E-POSTA] Bildirim e-postası kuyruğa alındı: Alıcı(lar)=%s, Konu='%s'", recipients, subject)

        worker_thread = threading.Thread(
            target=_async_email_worker,
            args=(subject, message, recipient_list, html_message),
            daemon=True
        )
        worker_thread.start()






