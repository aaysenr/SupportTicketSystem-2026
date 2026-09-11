from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Canlı ve test ortamı için SMTP e-posta ayarlarını test eder.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Test e-postasının gönderileceği alıcı adresi')

    def handle(self, *args, **options):
        recipient = options['email']
        backend = getattr(settings, 'EMAIL_BACKEND', 'Bilinmiyor')
        host = getattr(settings, 'EMAIL_HOST', 'Console (Terminal)')
        port = getattr(settings, 'EMAIL_PORT', '-')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@desteksistemi.com')

        self.stdout.write(self.style.NOTICE(f"E-Posta Servisi Test Ediliyor..."))
        self.stdout.write(f"Aktif Backend : {backend}")
        self.stdout.write(f"Sunucu (Host) : {host}:{port}")
        self.stdout.write(f"Gönderen       : {from_email}")
        self.stdout.write(f"Alıcı          : {recipient}")

        try:
            subject = "[Destek Sistemi] Canlı SMTP Test E-Postası"
            message = (
                f"Merhaba,\n\n"
                f"Bu bir test e-postasıdır. Destek Talep Sistemi e-posta servisi başarıyla yapılandırılmıştır.\n\n"
                f"Backend: {backend}\n"
                f"Host: {host}:{port}\n\n"
                f"İyi çalışmalar dileriz."
            )

            result = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False
            )

            if result == 1:
                self.stdout.write(self.style.SUCCESS(f"Tebrikler! Test e-postası başarıyla gönderildi: {recipient}"))
            else:
                self.stdout.write(self.style.WARNING("E-posta gönderim fonksiyonu 0 döndürdü."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"HATA: E-posta gönderilemedi! Hata detayı: {e}"))
