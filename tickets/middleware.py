from django.shortcuts import render

class CustomErrorPageMiddleware:
    """
    Geliştirme (DEBUG=True) ve üretim ortamlarında, eşleşmeyen veya 404 dönen
    isteklerin Django'nun sarı URL listesi veren teknik geliştirici ekranı yerine,
    kullanıcının hazırladığı şık ve güvenli 404 hata şablonunu (404.html) göstermesini sağlar.
    Böylece sistemdeki gizli URL yapıları (örneğin super-admin/) dışarıya asla sızdırılmaz.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # 404 Sayfa Bulunamadı durumunu yakala
        if response.status_code == 404:
            # Statik dosya veya API JSON isteklerini bozmamak için filtrele
            if not request.path.startswith('/static/') and not request.path.startswith('/media/') and not request.path.startswith('/api/'):
                from tickets.views import custom_404_view
                return custom_404_view(request)

        # 403 Erişim Engellendi durumunu yakala
        elif response.status_code == 403:
            if not request.path.startswith('/static/') and not request.path.startswith('/media/') and not request.path.startswith('/api/'):
                from tickets.views import custom_403_view
                return custom_403_view(request)

        return response
