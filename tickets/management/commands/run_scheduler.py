import time
import signal
import sys
import logging
from datetime import datetime, timedelta
from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Destek Talep Sistemi için yerleşik arka plan zamanlayıcı (Scheduler Daemon).\n"
        "- check_sla_breaches: Her 15 dakikada bir çalıştırılır.\n"
        "- cleanup_unverified_accounts: Her 7 günde bir çalıştırılır."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-once',
            action='store_true',
            help='Görevleri bir kez çalıştırıp zamanlayıcı döngüsüne girmeden çıkar.',
        )
        parser.add_argument(
            '--interval-minutes',
            type=int,
            default=15,
            help='SLA ihlal denetimi aralığı (Varsayılan: 15 dakika).',
        )

    def handle(self, *args, **options):
        run_once = options.get('run_once', False)
        interval_sec = options.get('interval_minutes', 15) * 60

        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(self.style.SUCCESS("  DESTEK TALEP SİSTEMİ - ARKA PLAN ZAMANLAYICI BAŞLATILDI"))
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(f"  • SLA Denetimi Aralığı: {options.get('interval_minutes')} dakika")
        self.stdout.write("  • Pasif Hesap Temizliği Aralığı: 7 gün")
        self.stdout.write("  • Çıkmak için: Ctrl + C")
        self.stdout.write(self.style.SUCCESS("=" * 65 + "\n"))

        last_sla_check = None
        last_cleanup = None

        def shutdown_handler(signum, frame):
            self.stdout.write(self.style.WARNING("\nZamanlayıcı güvenle durduruluyor..."))
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, shutdown_handler)

        while True:
            now = datetime.now()

            # 1. SLA Süre Aşımı Kontrolü (Her 15 dakikada bir)
            if last_sla_check is None or (now - last_sla_check).total_seconds() >= interval_sec:
                self.stdout.write(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] SLA İhlal Denetimi çalıştırılıyor...")
                try:
                    call_command('check_sla_breaches')
                except Exception as e:
                    logger.error("check_sla_breaches çalıştırılırken hata: %s", e)
                last_sla_check = now

            # 2. Pasif ve Doğrulanmamış Hesap Temizliği (Haftada 1 kez)
            if last_cleanup is None or (now - last_cleanup) >= timedelta(days=7):
                self.stdout.write(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Pasif hesap temizliği çalıştırılıyor...")
                try:
                    call_command('cleanup_unverified_accounts')
                except Exception as e:
                    logger.error("cleanup_unverified_accounts çalıştırılırken hata: %s", e)
                last_cleanup = now

            if run_once:
                self.stdout.write(self.style.SUCCESS("Tek seferlik çalıştırma tamamlandı."))
                break

            # 30 saniyelik uyku döngüsü ile kesintilere duyarlı bekleme
            time.sleep(30)
