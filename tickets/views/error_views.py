from django.shortcuts import render


def custom_404_view(request, exception=None):
    """Özel 404 Sayfa Bulunamadı hata ekranı."""
    return render(request, '404.html', status=404)




def custom_403_view(request, exception=None):
    """Özel 403 Erişim Yetkisi Yok hata ekranı."""
    return render(request, '403.html', status=403)




def custom_500_view(request):
    """Özel 500 Sunucu Hatası ekranı."""
    return render(request, '500.html', status=500)




