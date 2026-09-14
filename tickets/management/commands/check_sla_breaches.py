from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from tickets.models import Ticket, Notification, TicketActivityLog
from tickets.webhooks import send_outgoing_webhook
from tickets.views.common import send_notification_email


class Command(BaseCommand):
    help = 'SLA süresi aşılmış aktif destek taleplerini tespit eder, uyarı bildirimi gönderir ve webhookları tetikler.'

    def handle(self, *args, **options):
        now = timezone.now()
        breached_tickets = Ticket.objects.filter(
            status__in=['open', 'in_progress'],
            first_response_at__isnull=True,
            sla_deadline__lt=now,
            sla_deadline__isnull=False
        ).select_related('assigned_to', 'created_by')

        breached_count = 0
        notified_count = 0

        for ticket in breached_tickets:
            breached_count += 1
            # Daha önce SLA uyarısı kaydedilmiş mi kontrol et
            already_notified = TicketActivityLog.objects.filter(
                ticket=ticket,
                action__contains="SLA Süresi Aşıldı!"
            ).exists()

            if not already_notified:
                # Webhook tetikle
                try:
                    send_outgoing_webhook(ticket, event_type="sla_breached")
                except Exception:
                    pass

                # Bildirim gönder
                if ticket.assigned_to:
                    Notification.objects.create(
                        recipient=ticket.assigned_to,
                        ticket=ticket,
                        message=f"⚠️ #{ticket.ticket_number} talebinin SLA hedef süresi aşıldı!"
                    )
                    if ticket.assigned_to.email:
                        send_notification_email(
                            subject=f"[SLA İHLALİ] #{ticket.ticket_number} Talebinin Süresi Aşıldı",
                            message=(
                                f"Merhaba {ticket.assigned_to.username},\n\n"
                                f"Sorumlusu olduğunuz #{ticket.ticket_number} numaralı '{ticket.title}' "
                                f"talebinin SLA hedef süresi aşılmıştır. Lütfen en kısa sürede yanıt veriniz."
                            ),
                            recipient_list=[ticket.assigned_to.email]
                        )
                else:
                    # Atanmamış talep ise tüm süper yöneticilere bildir
                    for admin in User.objects.filter(is_superuser=True):
                        Notification.objects.create(
                            recipient=admin,
                            ticket=ticket,
                            message=f"⚠️ Atanmamış #{ticket.ticket_number} talebinin SLA hedef süresi aşıldı!"
                        )

                # Aktivite günlüğüne işle
                TicketActivityLog.objects.create(
                    ticket=ticket,
                    actor=None,
                    action="⚠️ SLA Süresi Aşıldı! Sistem tarafından gecikme uyarısı ve webhook tetiklendi."
                )
                notified_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"SLA denetimi tamamlandı: {breached_count} adet gecikmiş talep incelendi, {notified_count} yeni bildirim gönderildi."
            )
        )
