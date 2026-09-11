import os
from django.core.exceptions import ValidationError

try:
    from PIL import Image
except ImportError:
    Image = None

# İzin verilen güvenli dosya uzantıları
ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf', '.zip', '.log']

# Maksimum dosya boyutu: 10 MB (10 * 1024 * 1024 bayt)
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Bilinen dosya tiplerinin ilk bayt (magic bytes) imzaları
MAGIC_SIGNATURES = {
    '.pdf': [b'%PDF'],
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
}


def validate_file_security(file):
    """
    Yüklenen dosyaların boyutunu, uzantısını ve içerik sihirli baytlarını (magic bytes)
    denetleyen gelişmiş güvenlik doğrulayıcısı.
    - Maksimum 10 MB dosya boyutuna izin verir.
    - Sadece güvenli uzantılara (.png, .jpg, .jpeg, .pdf, .zip, .log) izin verir.
    - Sahte uzantılı dosyaları (örn. php veya exe dosyasının .jpg yapılması) magic bytes ile yakalar.
    - Görselleri Pillow ile derinlemesine doğrular.
    """
    if not file:
        return

    # 1. Dosya Boyutu Kontrolü
    if file.size > MAX_FILE_SIZE_BYTES:
        current_size_mb = round(file.size / (1024 * 1024), 2)
        raise ValidationError(
            f"Yüklenen dosya boyutu çok büyük ({current_size_mb} MB). "
            f"Maksimum izin verilen dosya boyutu {MAX_FILE_SIZE_MB} MB'tır."
        )

    # 2. Dosya Uzantısı Kontrolü
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_list_str = ", ".join(ALLOWED_EXTENSIONS)
        raise ValidationError(
            f"'{ext}' uzantılı dosya yüklenemez. "
            f"Yalnızca şu uzantılara izin verilmektedir: {allowed_list_str}"
        )

    # 3. Magic Bytes (İçerik İmzası) Kontrolü
    if ext in MAGIC_SIGNATURES:
        signatures = MAGIC_SIGNATURES[ext]
        max_sig_len = max(len(s) for s in signatures)
        try:
            file.seek(0)
            header = file.read(max_sig_len)
            file.seek(0)
            if not any(header.startswith(sig) for sig in signatures):
                raise ValidationError(
                    f"Güvenlik Uyarısı: '{file.name}' dosyasının içeriği belirtilen '{ext}' uzantısıyla uyuşmuyor."
                )
        except ValidationError:
            raise
        except Exception:
            raise ValidationError("Dosya içeriği doğrulanamadı veya dosya bozuk.")

    # 4. Görseller için Pillow İle Derinlikli Doğrulama
    if ext in ['.png', '.jpg', '.jpeg'] and Image:
        try:
            file.seek(0)
            img = Image.open(file)
            img.verify()
            file.seek(0)
        except ValidationError:
            raise
        except Exception:
            raise ValidationError("Geçersiz veya bozuk görsel dosyası yüklendi.")
    elif ext == '.log':
        # Log dosyası düz metin olmalı, binary/zararlı çalıştırılabilir kod içermemeli
        try:
            file.seek(0)
            chunk = file.read(2048)
            file.seek(0)
            if b'\x00' in chunk:
                raise ValidationError("Geçersiz metin/log dosyası: İkili (binary) kod tespit edildi.")
        except ValidationError:
            raise
        except Exception:
            raise ValidationError("Log dosyası doğrulanamadı.")
