import os
from django.core.exceptions import ValidationError

# İzin verilen güvenli dosya uzantıları
ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf', '.zip', '.log']

# Maksimum dosya boyutu: 10 MB (10 * 1024 * 1024 bayt)
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def validate_file_security(file):
    """
    Yüklenen dosyaların boyutunu ve uzantısını denetleyen güvenlik doğrulayıcısı.
    - Maksimum 10 MB dosya boyutuna izin verir.
    - Sadece güvenli uzantılara (.png, .jpg, .jpeg, .pdf, .zip, .log) izin verir.
    - Çalıştırılabilir ve zararlı betik dosyalarını (exe, bat, sh, php vb.) engeller.
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
