from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages

from ..models import Notification


@login_required
def notifications_list_view(request):
    notifications = Notification.objects.filter(recipient=request.user).select_related('actor', 'ticket')
    return render(request, 'tickets/notifications.html', {'notifications': notifications})



@login_required
def mark_notification_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    if notification.ticket:
        return redirect('ticket_detail', pk=notification.ticket.pk)
    return redirect('notifications_list')




@login_required
@require_POST
def mark_all_notifications_as_read(request):
    """
    Kullanıcının tüm okunmamış bildirimlerini tek tıkla okundu olarak işaretler.
    Güvenlik: Yalnızca CSRF korumalı POST ve AJAX isteklerini kabul eder.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "Tüm bildirimleriniz başarıyla okundu olarak işaretlendi.")
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'notifications_list'
    return redirect(next_url)




@login_required
@require_POST
def delete_notification(request, pk):
    """
    Kullanıcının seçili bildirimini siler.
    Güvenlik: Yalnızca CSRF korumalı POST ve AJAX isteklerini kabul eder.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'status': 'success', 'message': 'Bildirim silindi.'})
    messages.success(request, "Bildirim silindi.")
    return redirect('notifications_list')




@login_required
@require_POST
def delete_all_notifications(request):
    """
    Kullanıcının tüm bildirimlerini siler.
    Güvenlik: Yalnızca CSRF korumalı POST ve AJAX isteklerini kabul eder.
    """
    count, _ = Notification.objects.filter(recipient=request.user).delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'status': 'success', 'deleted_count': count})
    messages.success(request, f"Tüm bildirimleriniz ({count} adet) silindi.")
    return redirect('notifications_list')


   


