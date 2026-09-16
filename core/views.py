from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from employees.models import Employe, StatutEmploye


class RedirectionDashboardView(LoginRequiredMixin, View):
    """
    Point d'entree unique apres connexion : redirige vers le tableau de bord
    adapte au role de l'utilisateur (RG-02).
    """
    def get(self, request):
        user = request.user
        if user.doit_changer_mot_de_passe:
            return redirect("accounts:changer_mot_de_passe")
        if user.est_admin:
            return redirect("core:dashboard_admin")
        if user.est_rh:
            return redirect("core:dashboard_rh")
        return redirect("core:dashboard_employe")


class DashboardAdminView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_admin.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # BF-RH-17 : indicateurs (effectif, absenteisme, turnover, conges acceptes).
        # Version simplifiee au Jour 1 ; sera enrichie au Jour 4 (app analytics).
        ctx["effectif_total"] = Employe.objects.filter(statut=StatutEmploye.ACTIF).count()
        return ctx


class DashboardRHView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_rh.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["effectif_total"] = Employe.objects.filter(statut=StatutEmploye.ACTIF).count()
        return ctx


class DashboardEmployeView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_employe.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["fiche"] = getattr(self.request.user, "fiche_employe", None)
        return ctx
