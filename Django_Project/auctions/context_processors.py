from .models import Category, Notification


def marketplace_context(request):
    top_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children')
    unread_notifications = 0
    latest_notifications = []

    if request.user.is_authenticated:
        notification_queryset = Notification.objects.filter(user=request.user).select_related('auction')
        unread_notifications = notification_queryset.filter(is_read=False).count()
        latest_notifications = list(notification_queryset[:4])

    return {
        'nav_categories': top_categories,
        'latest_notifications': latest_notifications,
        'unread_notifications': unread_notifications,
    }
