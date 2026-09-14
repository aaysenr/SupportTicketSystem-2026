from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone


class Command(BaseCommand):
    help = 'E-posta doğrulamasını tamamlamamış ve süresi dolmuş pasif kullanıcı hesaplarını temizler.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Kaç günden eski onaylanmamış hesapların temizleneceğini belirtir (varsayılan: 7 gün).'
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)

        unverified_users = User.objects.filter(
            is_active=False,
            is_staff=False,
            is_superuser=False,
            date_joined__lt=cutoff,
            tickets__isnull=True,
            email_verification__isnull=False
        ).exclude(username__startswith='deleted_user_')
        count = unverified_users.count()
        unverified_users.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"{days} günden eski {count} adet onaylanmamış pasif hesap temizlendi."
            )
        )
