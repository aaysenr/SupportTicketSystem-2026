from .models import Notification

def notifications_context(request):
    """
    Tüm HTML sayfalarında Navbar'daki bildirim zili için okunmamış sayı ve bildirim listesi döndürür.
    """
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False)
        recent_notifications = Notification.objects.filter(recipient=request.user)[:5]
        return {
            'unread_notifications_count': unread_notifications.count(),
            'recent_notifications': recent_notifications
        }
    return {
        'unread_notifications_count': 0,
        'recent_notifications': []
    }
