from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import ListView, TemplateView, View

from accounts.mixins import droit_requis
from accounts.models import Utilisateur
from .forms import NotificationForm
from .models import (
    ActivityLog, CategorieNotification, Notification, TypeAction, log_activity,
)


def notifications_recues(user):
    """Notifications visibles par `user` : personnelles, ou diffusions sans destinataire precis."""
    return Notification.objects.filter(
        models.Q(destinataire=user)
        | (models.Q(destinataire__isnull=True) & models.Q(role_cible__in=["TOUS", user.role]))
    ).distinct()


class MesNotificationsView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "notifications/mes_notifications.html"
    context_object_name = "notifications"
    paginate_by = 10

    def _onglet(self):
        return "envoyees" if self.request.GET.get("onglet") == "envoyees" else "recues"

    def get_queryset(self):
        user = self.request.user
        if self._onglet() == "envoyees":
            return Notification.objects.filter(expediteur=user).select_related("destinataire")
        qs = notifications_recues(user).select_related("expediteur")
        filtre = self.request.GET.get("filtre", "")
        if filtre == "non_lues":
            qs = qs.filter(lu=False)
        elif filtre in dict(CategorieNotification.choices):
            qs = qs.filter(categorie=filtre)
        return qs.order_by("-date_creation")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        recues = notifications_recues(user)
        ctx["onglet"] = self._onglet()
        ctx["filtre"] = self.request.GET.get("filtre", "")
        ctx["nb_total"] = recues.count()
        ctx["non_lues"] = recues.filter(lu=False).count()
        ctx["compteurs_categories"] = [
            (valeur, libelle, recues.filter(categorie=valeur).count())
            for valeur, libelle in CategorieNotification.choices
            if recues.filter(categorie=valeur).exists()
        ]
        ctx["peut_envoyer"] = user.a_droit("notifications", "creation")
        ctx["form"] = kwargs.get("form") or NotificationForm()
        ctx["ouvrir_formulaire"] = bool(kwargs.get("form")) or self.request.GET.get("nouvelle") == "1"
        voir = self.request.GET.get("voir")
        ctx["detail"] = recues.filter(pk=voir).select_related("expediteur").first() if voir else None
        return ctx


class MarquerNotificationLueView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(notifications_recues(request.user), pk=pk)
        notification.lu = True
        notification.save(update_fields=["lu"])
        return redirect(request.POST.get("retour") or "notifications:mes_notifications")


class ToutMarquerLuView(LoginRequiredMixin, View):
    def post(self, request):
        notifications_recues(request.user).filter(destinataire=request.user, lu=False).update(lu=True)
        messages.success(request, "Toutes vos notifications sont marquées comme lues.")
        return redirect("notifications:mes_notifications")


class SupprimerNotificationView(LoginRequiredMixin, View):
    """Chacun ne supprime que les notifications qui lui sont adressees personnellement."""

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, destinataire=request.user)
        notification.delete()
        messages.success(request, "Notification supprimée.")
        return redirect("notifications:mes_notifications")


class HistoriqueNotificationsView(droit_requis("notifications", "creation"), TemplateView):
    template_name = "notifications/historique_notifications.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filtre = Q(action__icontains="notification") | Q(details__icontains="notification")
        ctx["historique"] = ActivityLog.objects.filter(filtre).order_by("-date_creation")[:200]
        return ctx


class EnvoyerNotificationView(droit_requis("notifications", "creation", "creation"), View):
    """Envoi d'une notification interne (Administrateur / Responsable RH, BF-ADM09, BF-RH-21)."""

    def post(self, request):
        form = NotificationForm(request.POST)
        if not form.is_valid():
            vue = MesNotificationsView()
            vue.setup(request)
            vue.object_list = vue.get_queryset()
            return vue.render_to_response(vue.get_context_data(form=form))

        data = form.cleaned_data
        cible = data["cible"]
        if cible == "PERSONNE":
            destinataires = [data["destinataire"]]
        else:
            base = Utilisateur.objects.filter(is_active=True).exclude(pk=request.user.pk)
            if cible == "TOUS":
                destinataires = list(base)
            elif cible in ("EMPLOYE", "RH", "ADMIN"):
                destinataires = list(base.filter(role=cible))
            else:
                destinataires = list(base.filter(fiche_employe__service=data["departement"]))

        for user in destinataires:
            Notification.objects.create(
                expediteur=request.user, destinataire=user, role_cible="TOUS",
                titre=data["titre"], message=data["message"], categorie=data["categorie"],
            )
        log_activity(request.user, "Notification envoyee", f"{data['titre']} ({len(destinataires)} destinataire(s)).")
        messages.success(request, f"Notification envoyée à {len(destinataires)} utilisateur(s).")
        return redirect("notifications:mes_notifications")


# ---------------------------------------------------------------------------
# Journal d'activite (BF-ADM06)
# ---------------------------------------------------------------------------
class JournalActiviteView(droit_requis("journaux"), TemplateView):
    template_name = "notifications/journal_activite.html"
    PAR_PAGE = 15

    PERIODES = [("today", "Aujourd'hui"), ("7", "7 derniers jours"), ("30", "30 derniers jours"), ("", "Tout")]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        get = self.request.GET
        qs = ActivityLog.objects.select_related("utilisateur")
        periode = get.get("periode", "today")
        maintenant = timezone.localtime()
        debut_jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
        if periode == "today":
            qs = qs.filter(date_creation__gte=debut_jour)
        elif periode in ("7", "30"):
            qs = qs.filter(date_creation__gte=debut_jour - timedelta(days=int(periode) - 1))
        utilisateur = get.get("utilisateur", "")
        if utilisateur.isdigit():
            qs = qs.filter(utilisateur_id=int(utilisateur))
        type_action = get.get("type", "")
        if type_action in dict(TypeAction.choices):
            qs = qs.filter(type_action=type_action)
        recherche = get.get("q", "").strip()
        if recherche:
            qs = qs.filter(Q(action__icontains=recherche) | Q(details__icontains=recherche))

        total = qs.count()
        page = max(int(get.get("page", 1)) if get.get("page", "1").isdigit() else 1, 1)
        debut = (page - 1) * self.PAR_PAGE
        evenements = list(qs[debut:debut + self.PAR_PAGE])

        aujourdhui = ActivityLog.objects.filter(date_creation__gte=debut_jour)
        detail = None
        if get.get("evenement", "").isdigit():
            detail = ActivityLog.objects.select_related("utilisateur").filter(pk=int(get["evenement"])).first()

        ctx.update({
            "evenements": evenements, "total": total, "page": page,
            "nb_pages": max((total + self.PAR_PAGE - 1) // self.PAR_PAGE, 1),
            "nb_actions_aujourdhui": aujourdhui.count(),
            "nb_alertes_aujourdhui": aujourdhui.filter(resultat="ALERTE").count(),
            "nb_utilisateurs_actifs": Utilisateur.objects.filter(is_active=True).count(),
            "periodes": self.PERIODES, "periode": periode,
            "utilisateurs": Utilisateur.objects.order_by("last_name", "first_name"),
            "utilisateur_filtre": utilisateur,
            "types": TypeAction.choices, "type_filtre": type_action,
            "recherche": recherche, "detail": detail,
        })
        return ctx
