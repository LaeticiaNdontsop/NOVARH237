from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, TemplateView
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy

from accounts.mixins import AdminOuRHRequiredMixin, AdminRequiredMixin
from employees.models import Employe, StatutEmploye
from demandes.models import DemandeConge, StatutDemande, Absence, StatutAbsence, Demission, StatutDemission
from notifications.models import ActivityLog, Notification
from analytics import indicateurs
from .forms import CandidatureForm, EvaluationForm, FormationForm, OffreForm
from .models import Candidature, Evaluation, Formation, Offre, StatutOffre


class AccueilView(TemplateView):
    """
    Page d'accueil publique (vitrine). Un utilisateur deja connecte est renvoye
    directement vers son tableau de bord.
    """
    template_name = "core/accueil.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:redirection_dashboard")
        return super().dispatch(request, *args, **kwargs)


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
        # Version simplifiee au Jour 2 ; enrichie au Jour 4 (app analytics).
        ctx["effectif_total"] = Employe.objects.filter(statut=StatutEmploye.ACTIF).count()
        ctx["demandes_a_decider"] = DemandeConge.objects.filter(
            statut=StatutDemande.EN_ATTENTE_ADMIN, admin_assigne=self.request.user
        ).count()
        ctx["demissions_a_traiter"] = Demission.objects.filter(statut=StatutDemission.TRANSMISE_ADMIN).count()
        ctx["turnover_12_mois"] = indicateurs.turnover()
        return ctx


class DashboardRHView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_rh.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["effectif_total"] = Employe.objects.filter(statut=StatutEmploye.ACTIF).count()
        ctx["demandes_a_traiter"] = DemandeConge.objects.filter(
            statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=self.request.user
        ).count()
        ctx["absences_a_valider"] = Absence.objects.filter(statut=StatutAbsence.EN_ATTENTE).count()
        ctx["demissions_en_cours"] = Demission.objects.exclude(statut=StatutDemission.COMMUNIQUEE).count()
        return ctx


class DashboardEmployeView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_employe.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fiche = getattr(self.request.user, "fiche_employe", None)
        ctx["fiche"] = fiche
        if fiche is not None:
            ctx["mes_demandes_en_cours"] = DemandeConge.objects.filter(employe=fiche).exclude(
                statut__in=["APPROUVEE", "REJETEE_RH", "REJETEE_ADMIN"]
            ).count()
        return ctx


class EvaluationsFormationsView(AdminOuRHRequiredMixin, TemplateView):
    template_name = "core/evaluations_formations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["evaluations"] = Evaluation.objects.select_related("employe__utilisateur").all()
        ctx["formations"] = Formation.objects.prefetch_related("participants").all()
        ctx["evaluation_form"] = EvaluationForm()
        ctx["formation_form"] = FormationForm()
        return ctx


class CreerEvaluationView(AdminOuRHRequiredMixin, CreateView):
    model = Evaluation
    form_class = EvaluationForm
    template_name = "core/evaluation_form.html"
    success_url = reverse_lazy("core:evaluations_formations")

    def form_valid(self, form):
        form.instance.creee_par = self.request.user
        messages.success(self.request, "Evaluation enregistree.")
        return super().form_valid(form)


class CreerFormationView(AdminOuRHRequiredMixin, CreateView):
    model = Formation
    form_class = FormationForm
    template_name = "core/formation_form.html"
    success_url = reverse_lazy("core:evaluations_formations")

    def form_valid(self, form):
        form.instance.creee_par = self.request.user
        messages.success(self.request, "Formation planifiee.")
        return super().form_valid(form)


class RecrutementsView(AdminOuRHRequiredMixin, TemplateView):
    template_name = "core/recrutements.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["candidatures"] = Candidature.objects.select_related("offre").all()
        return ctx


class OffresView(LoginRequiredMixin, TemplateView):
    template_name = "core/offres.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.est_admin or self.request.user.est_rh:
            offres = Offre.objects.all()
            ctx["offre_form"] = OffreForm()
        else:
            offres = Offre.objects.filter(statut=StatutOffre.PUBLIEE)
        ctx["offres"] = offres
        ctx["candidature_form"] = CandidatureForm()
        return ctx


class CreerOffreView(AdminOuRHRequiredMixin, CreateView):
    model = Offre
    form_class = OffreForm
    template_name = "core/offre_form.html"
    success_url = reverse_lazy("core:offres")

    def form_valid(self, form):
        form.instance.creee_par = self.request.user
        messages.success(self.request, "Offre enregistree.")
        return super().form_valid(form)


@method_decorator(require_POST, name="dispatch")
class PostulerOffreView(LoginRequiredMixin, View):
    def post(self, request, pk):
        offre = get_object_or_404(Offre, pk=pk, statut=StatutOffre.PUBLIEE)
        if not request.user.est_employe:
            raise PermissionDenied("Seul un employe peut postuler a une offre.")
        form = CandidatureForm(request.POST, request.FILES)
        if form.is_valid():
            candidature = form.save(commit=False)
            candidature.offre = offre
            candidature.save()
            messages.success(request, "Votre candidature a ete enregistree.")
        else:
            messages.error(request, "Verifiez les informations de votre candidature.")
        return redirect("core:offres")


@require_POST
def modifier_statut_candidature(request, pk):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if not (request.user.est_admin or request.user.est_rh):
        raise PermissionDenied
    candidature = get_object_or_404(Candidature, pk=pk)
    statut = request.POST.get("statut")
    if statut not in dict(candidature._meta.get_field("statut").choices):
        messages.error(request, "Statut de candidature invalide.")
    else:
        candidature.statut = statut
        candidature.save(update_fields=["statut"])
        messages.success(request, "Statut de candidature mis a jour.")
    return redirect("core:recrutements")


class RolesDroitsView(AdminRequiredMixin, TemplateView):
    template_name = "core/roles_droits.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["roles"] = [
            {"nom": "Administrateur", "droits": ["Créer les comptes", "Valider les demandes", "Accéder au journal d’activité", "Gérer les rôles"]},
            {"nom": "Responsable RH", "droits": ["Gérer les fiches employe", "Traiter les congés et absences", "Consulter les évaluations", "Envoyer notifications"]},
            {"nom": "Employé", "droits": ["Consulter son profil", "Déclarer une demande", "Voir ses documents et rémunérations", "Recevoir des notifications"]},
        ]
        return ctx


class JournalActiviteView(AdminRequiredMixin, TemplateView):
    template_name = "core/journal_activite.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["activites"] = list(ActivityLog.objects.select_related("utilisateur").order_by("-date_creation")[:20])
        ctx["notifications_recentes"] = list(Notification.objects.select_related("expediteur", "destinataire").order_by("-date_creation")[:10])
        return ctx
