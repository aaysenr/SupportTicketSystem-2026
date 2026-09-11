import base64
import hmac
import hashlib
import io
import secrets
import struct
import time
import urllib.parse
try:
    import qrcode
except ImportError:
    qrcode = None


def generate_totp_secret() -> str:
    """RFC 6238 uyumlu 32 karakterlik rastgele Base32 gizli anahtar üretir."""
    random_bytes = secrets.token_bytes(20)
    return base64.b32encode(random_bytes).decode('utf-8').replace('=', '')


def get_totp_token(secret: str, for_time: float = None, interval: int = 30, digits: int = 6) -> str:
    """Belirtilen zaman ve gizli anahtar için 6 haneli TOTP kodu üretir."""
    if for_time is None:
        for_time = time.time()

    counter = int(for_time // interval)
    counter_bytes = struct.pack(">Q", counter)

    # Base32 padding tamamla
    padding_needed = (8 - len(secret) % 8) % 8
    secret_padded = secret.upper() + ("=" * padding_needed)
    key = base64.b32decode(secret_padded, casefold=True)

    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = hmac_hash[-1] & 0x0F
    code_int = struct.unpack(">I", hmac_hash[offset:offset + 4])[0] & 0x7FFFFFFF
    token = str(code_int % (10 ** digits)).zfill(digits)
    return token


def verify_totp_token(secret: str, token: str, window: int = 1, interval: int = 30) -> bool:
    """
    Kullanıcının girdiği 6 haneli kodu doğrular.
    Zaman senkronizasyonu kaymalarına karşı (-window, +window) aralığını tolerans olarak kabul eder.
    """
    if not secret or not token:
        return False

    token = str(token).strip()
    if not token.isdigit() or len(token) != 6:
        return False

    now = time.time()
    for w in range(-window, window + 1):
        test_time = now + (w * interval)
        if hmac.compare_digest(get_totp_token(secret, for_time=test_time, interval=interval), token):
            return True
    return False


def get_totp_uri(secret: str, username: str, issuer: str = "Support Ticket System") -> str:
    """Google Authenticator / Authy için 'otpauth://' standardında URI oluşturur."""
    label = f"{issuer}:{username}"
    params = {
        'secret': secret,
        'issuer': issuer,
        'algorithm': 'SHA1',
        'digits': '6',
        'period': '30'
    }
    return f"otpauth://totp/{urllib.parse.quote(label)}?{urllib.parse.urlencode(params)}"


def generate_qr_code_data_uri(uri: str) -> str:
    """TOTP URI'si için base64 kodlu PNG veri URI'si (Data URI) üretir."""
    if not qrcode:
        return ""

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=3,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e293b", back_color="#ffffff")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f"data:image/png;base64,{b64_str}"
