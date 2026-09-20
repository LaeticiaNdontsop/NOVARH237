from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, View, TemplateView

from accounts.mixins import AdminOuRHRequiredMixin
from .forms import NotificationForm
from .models import ActivityLog, Notification, log_activity


class HistoriqueNotificationsView(AdminOuRHRequiredMixin, TemplateView):
    template_name = "notifications/historique_notifications.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filtre = Q(action__icontains="notification") | Q(details__icontains="notification")
        ctx["historique"] = ActivityLog.objects.filter(filtre).order_by("-date_creation")[:200]
        return ctx


class MesNotificationsView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "notifications/mes_notifications.html"
    context_object_name = "notifications"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(
            models.Q(destinataire=user) | models.Q(destinataire__isnull=True) | models.Q(role_cible=user.role)
        ).distinct().order_by("-date_creation")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["non_lues"] = Notification.objects.filter(
            models.Q(destinataire=user) | models.Q(destinataire__isnull=True) | models.Q(role_cible=user.role)
        ).filter(lu=False).count()
        ctx["form"] = NotificationForm()
        if user.est_admin:
            ctx["peut_envoyer"] = True
        elif user.est_rh:
            ctx["peut_envoyer"] = True
        else:
            ctx["peut_envoyer"] = False
        return ctx


class MarquerNotificationLueView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        if notification.destinataire_id != request.user.id and notification.destinataire_id is not None:
            return redirect("notifications:mes_notifications")
        notification.lu = True
        notification.save(update_fields=["lu"])
        return redirect("notifications:mes_notifications")


class EnvoyerNotificationView(AdminOuRHRequiredMixin, View):
    """Vue utilitaire pour l'envoi d'une notification depuis l'admin/RH."""
    def post(self, request):
        form = NotificationForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Le message est invalide.")
            return redirect("notifications:mes_notifications")

        message = form.cleaned_data["message"]
        role = form.cleaned_data["role_cible"]
        destinataire = form.cleaned_data["destinataire"]

        if destinataire:
            Notification.objects.create(
                expediteur=request.user,
                destinataire=destinataire,
                role_cible=role,
                message=message,
            )
            messages.success(request, "Notification envoyee au destinataire selectionne.")
        else:
            users = []
            if role == "TOUS":
                users = list(request.user.__class__.objects.exclude(id=request.user.id))
            elif role == "EMPLOYE":
                users = list(request.user.__class__.objects.filter(role="EMPLOYE"))
            elif role == "RH":
                users = list(request.user.__class__.objects.filter(role="RH"))
            elif role == "ADMIN":
                users = list(request.user.__class__.objects.filter(role="ADMIN"))

            for user in users:
                Notification.objects.create(
                    expediteur=request.user,
                    destinataire=user,
                    role_cible=role,
                    message=message,
                )
            messages.success(request, f"Notification envoyee a {len(users)} utilisateur(s).")

        log_activity(
            request.user,
            "Notification envoyee",
            message[:255],
        )
        return redirect("notifications:mes_notifications")
