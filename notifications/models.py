from django.conf import settings
from django.db import models


def log_activity(utilisateur, action, details=""):
    return ActivityLog.objects.create(utilisateur=utilisateur, action=action, details=details)


class Notification(models.Model):
    """Notification interne simple, utile pour les messages et alertes RH."""
    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_envoyees",
    )
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications_reçues",
        null=True,
        blank=True,
    )
    role_cible = models.CharField(
        max_length=10,
        choices=[
            ("TOUS", "Tous"),
            ("EMPLOYE", "Employes"),
            ("RH", "Responsables RH"),
            ("ADMIN", "Administrateurs"),
        ],
        default="TOUS",
    )
    message = models.TextField()
    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return self.message[:80]


class ActivityLog(models.Model):
    """Journal d'activite centralise pour l'admin."""
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=120)
    details = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Journal d'activite"
        verbose_name_plural = "Journaux d'activite"

    def __str__(self):
        return f"{self.action} - {self.utilisateur or 'Systeme'}"
