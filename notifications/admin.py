from django.contrib import admin

from .models import ActivityLog, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("message", "expediteur", "destinataire", "role_cible", "lu", "date_creation")
    list_filter = ("lu", "role_cible", "date_creation")
    search_fields = ("message", "expediteur__username", "destinataire__username")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "utilisateur", "details", "date_creation")
    list_filter = ("action", "date_creation")
    search_fields = ("action", "details", "utilisateur__username")
