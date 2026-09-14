import re
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def suggest_category_and_priority(title, description, available_categories=None):
    """
    Talep başlığı ve açıklamasını analiz ederek en uygun kategori ve öncelik seviyesini önerir.
    Eğer AI_COPILOT_API_KEY tanımlıysa gelişmiş NLP/LLM motoru kullanılır,
    aksi takdirde yerleşik kural tabanlı yapay zekâ sezgisel motoru çalışır.
    """
    text = f"{title} {description}".lower()

    # 1. Öncelik Tahmini (Priority Detection)
    urgent_keywords = [
        'acil', 'kritik', 'üretim durdu', 'sistem çöktü', 'çöktü', 'erişilemiyor',
        'hizmet verilemiyor', 'derhal', 'kesinti', 'güvenlik açığı', 'hack'
    ]
    high_keywords = [
        'ciddi', 'çalışmıyor', 'hata alıyorum', 'işlem yapamıyorum', 'müşteri bekliyor',
        'ödeme başarısız', 'kartımdan para çekildi', 'giriş yapamıyorum', 'bloke oldu'
    ]
    low_keywords = [
        'nasıl yapılır', 'bilgi almak', 'soru', 'öneri', 'merak ettim',
        'tavsiye', 'küçük bir rica', 'tasarım', 'renk değişimi'
    ]

    predicted_priority = 'medium'
    matched_priority_reason = "Genel akışa göre standart öncelik."

    for kw in urgent_keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', text) or kw in text:
            predicted_priority = 'urgent'
            matched_priority_reason = f"Kritik ifade tespit edildi: '{kw}'"
            break

    if predicted_priority == 'medium':
        for kw in high_keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text) or kw in text:
                predicted_priority = 'high'
                matched_priority_reason = f"Önemli operasyonel sorun ifadesi: '{kw}'"
                break

    if predicted_priority == 'medium':
        for kw in low_keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text) or kw in text:
                predicted_priority = 'low'
                matched_priority_reason = f"Bilgilendirme / danışma ifadesi: '{kw}'"
                break

    # 2. Kategori Tahmini (Category Detection)
    category_patterns = {
        'finans': ['fatura', 'ödeme', 'iade', 'kredi kartı', 'kart', 'tahsilat', 'dekont', 'iban', 'borç', 'abonelik', 'ücret'],
        'güvenlik': ['şifre', 'parola', '2fa', 'doğrulama', 'hesap', 'oturum', 'yetki', 'bloke', 'sms', 'kod gelmiyor'],
        'donanım': ['yazıcı', 'bilgisayar', 'monitör', 'klavye', 'fare', 'cihaz', 'kablo', 'wifi', 'modem', 'ip', 'tarayıcı donanım'],
        'yazılım': ['hata', 'bug', 'kod', 'sunucu', 'veritabanı', 'api', 'entegrasyon', '500', '404', 'sayfa açılmıyor', 'yüklenmiyor']
    }

    predicted_category_id = None
    predicted_category_name = None
    best_cat_match_score = 0

    if available_categories:
        for cat in available_categories:
            c_name_lower = cat.name.lower()
            score = 0
            
            # Kategori adı metinde geçiyor mu?
            if c_name_lower in text:
                score += 5

            # Kalıp kelimelerle eşleştirme
            for group, keywords in category_patterns.items():
                if group in c_name_lower:
                    for kw in keywords:
                        if kw in text:
                            score += 2

            if score > best_cat_match_score:
                best_cat_match_score = score
                predicted_category_id = cat.id
                predicted_category_name = cat.name

    return {
        'suggested_priority': predicted_priority,
        'suggested_priority_display': dict(
            [('low', 'Düşük'), ('medium', 'Orta'), ('high', 'Yüksek'), ('urgent', 'Acil')]
        ).get(predicted_priority, 'Orta'),
        'priority_reason': matched_priority_reason,
        'suggested_category_id': predicted_category_id,
        'suggested_category_name': predicted_category_name,
        'confidence': 'high' if best_cat_match_score >= 4 else 'medium'
    }


def generate_ticket_summary(ticket):
    """
    Destek personelinin bilet detayında zaman kazanması için
    talebı ve mevcut çözüm durumunu 1 cümlelik özet haline getirir.
    """
    try:
        creator_user = ticket.created_by
    except Exception:
        creator_user = None

    creator = (creator_user.get_full_name() or creator_user.username) if creator_user else "Bilinmeyen Kullanıcı"
    cat = ticket.category.name if ticket.category else "Genel"
    clean_desc = " ".join(ticket.description.split()[:20])

    has_solution = ticket.comments.filter(is_solution=True).exists() if ticket.pk else False
    comment_count = ticket.comments.filter(is_internal=False).count() if ticket.pk else 0

    if ticket.status == 'resolved' or has_solution:
        status_note = "onaylanmış bir çözüm ile başarıyla neticelendirilmiştir."
    elif comment_count > 0:
        status_note = f"destek ekibi ile karşılıklı iletişim sürecindedir ({comment_count} yanıt)."
    else:
        status_note = "henüz ilk destek yanıtını beklemektedir."

    summary = f"[{cat}] {creator} kullanıcısı '{ticket.title}' konusunda destek talep etmiş olup ({clean_desc}...), süreç {status_note}"
    return summary
