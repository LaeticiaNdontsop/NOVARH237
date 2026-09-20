from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, CreateView, TemplateView

from accounts.mixins import AdminOuRHRequiredMixin, RoleRequiredMixin
from notifications.models import ActivityLog, log_activity
from .forms import DemandeCongeForm, TraitementCommentaireForm, AbsenceForm, DemissionForm, PreavisForm
from .models import (
    DemandeConge, StatutDemande, DELAI_REAFFECTATION,
    Absence, StatutAbsence,
    Demission, StatutDemission,
    choisir_rh_disponible, reaffecter_demandes_expirees,
)


def _fiche_employe_ou_403(request):
    fiche = getattr(request.user, "fiche_employe", None)
    if fiche is None:
        raise PermissionDenied("Aucune fiche employe n'est associee a votre compte.")
    return fiche


def _historique_par_mots_cles(*mots_cles):
    filtre = Q()
    for mot in mots_cles:
        filtre |= Q(action__icontains=mot) | Q(details__icontains=mot)
    return ActivityLog.objects.filter(filtre).order_by("-date_creation")[:200]


# ---------------------------------------------------------------------------
# Espace Employe : conges & permissions
# ---------------------------------------------------------------------------
class HistoriqueCongesView(AdminOuRHRequiredMixin, TemplateView):
    template_name = "demandes/historique_conges.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["historique"] = _historique_par_mots_cles(
            "demande",
            "conge",
            "permission",
            "transmission d'une demande",
            "refus d'une demande",
            "approbation d'une demande",
            "cloture d'une demande",
        )
        return ctx


class MesDemandesCongeListView(LoginRequiredMixin, ListView):
    template_name = "demandes/mes_demandes.html"
    context_object_name = "demandes"
    paginate_by = 15

    def get_queryset(self):
        fiche = _fiche_employe_ou_403(self.request)
        return DemandeConge.objects.filter(employe=fiche)


class CreerDemandeCongeView(LoginRequiredMixin, CreateView):
    model = DemandeConge
    form_class = DemandeCongeForm
    template_name = "demandes/demande_conge_form.html"
    success_url = reverse_lazy("demandes:mes_demandes")

    def form_valid(self, form):
        fiche = _fiche_employe_ou_403(self.request)
        form.instance.employe = fiche
        form.instance.rh_assigne = choisir_rh_disponible()
        form.instance.date_limite_rh = timezone.now() + DELAI_REAFFECTATION
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Soumission d'une demande",
            f"Demande de {self.object.get_type_demande_display()} soumise pour {fiche.nom_complet}.",
        )
        messages.success(self.request, "Votre demande a ete soumise et transmise au Responsable RH.")
        return response


class DetailDemandeCongeView(LoginRequiredMixin, DetailView):
    model = DemandeConge
    template_name = "demandes/demande_conge_detail.html"
    context_object_name = "demande"

    def get_object(self, queryset=None):
        demande = get_object_or_404(DemandeConge, pk=self.kwargs["pk"])
        user = self.request.user
        if user.est_admin or user.est_rh or demande.employe.utilisateur_id == user.id:
            return demande
        raise PermissionDenied("Vous ne pouvez consulter que vos propres demandes.")


# ---------------------------------------------------------------------------
# Espace Responsable RH : traitement des conges/permissions (etapes 1 et 3)
# ---------------------------------------------------------------------------
class DemandesATraiterRHView(RoleRequiredMixin, ListView):
    """Etape 1 du circuit : demandes fraichement soumises, assignees a ce RH."""
    roles_autorises = ["RH"]
    template_name = "demandes/rh_a_traiter.html"
    context_object_name = "demandes"

    def get_queryset(self):
        reaffecter_demandes_expirees()
        return DemandeConge.objects.filter(
            statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=self.request.user
        )


class DemandesANotifierRHView(RoleRequiredMixin, ListView):
    """Etape 3 du circuit : demandes decidees par l'Admin, a cloturer/notifier."""
    roles_autorises = ["RH"]
    template_name = "demandes/rh_a_notifier.html"
    context_object_name = "demandes"

    def get_queryset(self):
        reaffecter_demandes_expirees()
        return DemandeConge.objects.filter(statut=StatutDemande.APPROUVEE_A_NOTIFIER, rh_assigne=self.request.user)


@login_required
@require_POST
def transmettre_a_admin(request, pk):
    if not request.user.est_rh:
        raise PermissionDenied
    demande = get_object_or_404(DemandeConge, pk=pk, statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=request.user)
    form = TraitementCommentaireForm(request.POST)
    commentaire = form.data.get("commentaire", "")
    demande.transmettre_a_admin(request.user, commentaire)
    log_activity(
        request.user,
        "Transmission d'une demande RH",
        f"Demande de {demande.get_type_demande_display()} transmise a l'Admin.",
    )
    messages.success(request, "Demande transmise a l'Administrateur pour decision.")
    return redirect("demandes:rh_a_traiter")


@login_required
@require_POST
def rejeter_par_rh(request, pk):
    if not request.user.est_rh:
        raise PermissionDenied
    demande = get_object_or_404(DemandeConge, pk=pk, statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=request.user)
    commentaire = request.POST.get("commentaire", "")
    demande.rejeter_par_rh(request.user, commentaire)
    log_activity(
        request.user,
        "Refus d'une demande RH",
        f"Demande de {demande.get_type_demande_display()} rejetee par le RH.",
    )
    messages.success(request, "Demande rejetee. L'employe sera informe du motif.")
    return redirect("demandes:rh_a_traiter")


@login_required
@require_POST
def cloturer_demande(request, pk):
    if not request.user.est_rh:
        raise PermissionDenied
    demande = get_object_or_404(
        DemandeConge, pk=pk, statut=StatutDemande.APPROUVEE_A_NOTIFIER, rh_assigne=request.user
    )
    demande.cloturer_par_rh()
    log_activity(
        request.user,
        "Cloture d'une demande RH",
        f"Demande de {demande.get_type_demande_display()} cloturee et notifiee a l'employe.",
    )
    messages.success(request, "Demande cloturee : l'employe est notifie de l'approbation.")
    return redirect("demandes:rh_a_notifier")


# ---------------------------------------------------------------------------
# Espace Administrateur : decision finale sur les conges/permissions (etape 2)
# ---------------------------------------------------------------------------
class DemandesAdminView(RoleRequiredMixin, ListView):
    roles_autorises = ["ADMIN"]
    template_name = "demandes/admin_a_decider.html"
    context_object_name = "demandes"

    def get_queryset(self):
        reaffecter_demandes_expirees()
        return DemandeConge.objects.filter(statut=StatutDemande.EN_ATTENTE_ADMIN, admin_assigne=self.request.user)


@login_required
@require_POST
def approuver_par_admin(request, pk):
    if not request.user.est_admin:
        raise PermissionDenied
    demande = get_object_or_404(
        DemandeConge, pk=pk, statut=StatutDemande.EN_ATTENTE_ADMIN, admin_assigne=request.user
    )
    commentaire = request.POST.get("commentaire", "")
    demande.approuver_par_admin(request.user, commentaire)
    log_activity(
        request.user,
        "Approbation d'une demande admin",
        f"Demande de {demande.get_type_demande_display()} approuvee par l'Admin.",
    )
    messages.success(request, "Demande approuvee. Le Responsable RH va notifier l'employe.")
    return redirect("demandes:admin_a_decider")


@login_required
@require_POST
def rejeter_par_admin(request, pk):
    if not request.user.est_admin:
        raise PermissionDenied
    demande = get_object_or_404(
        DemandeConge, pk=pk, statut=StatutDemande.EN_ATTENTE_ADMIN, admin_assigne=request.user
    )
    commentaire = request.POST.get("commentaire", "")
    demande.rejeter_par_admin(request.user, commentaire)
    log_activity(
        request.user,
        "Refus d'une demande admin",
        f"Demande de {demande.get_type_demande_display()} rejetee par l'Admin.",
    )
    messages.success(request, "Demande rejetee.")
    return redirect("demandes:admin_a_decider")


# ---------------------------------------------------------------------------
# Absences
# ---------------------------------------------------------------------------
class HistoriqueAbsencesView(AdminOuRHRequiredMixin, TemplateView):
    template_name = "demandes/historique_absences.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["historique"] = _historique_par_mots_cles(
            "absence",
            "validation d'une absence",
            "refus d'une absence",
            "declaration d'une absence",
        )
        return ctx


class MesAbsencesListView(LoginRequiredMixin, ListView):
    template_name = "demandes/mes_absences.html"
    context_object_name = "absences"

    def get_queryset(self):
        fiche = _fiche_employe_ou_403(self.request)
        return Absence.objects.filter(employe=fiche)


class CreerAbsenceView(LoginRequiredMixin, CreateView):
    model = Absence
    form_class = AbsenceForm
    template_name = "demandes/absence_form.html"
    success_url = reverse_lazy("demandes:mes_absences")

    def form_valid(self, form):
        fiche = _fiche_employe_ou_403(self.request)
        form.instance.employe = fiche
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Declaration d'une absence",
            f"Absence declaree pour {fiche.nom_complet} du {form.instance.date_debut} au {form.instance.date_fin}.",
        )
        messages.success(self.request, "Absence declaree, en attente de validation RH.")
        return response


class AbsencesRHView(RoleRequiredMixin, ListView):
    roles_autorises = ["RH"]
    template_name = "demandes/rh_absences.html"
    context_object_name = "absences"

    def get_queryset(self):
        return Absence.objects.filter(statut=StatutAbsence.EN_ATTENTE)


@login_required
@require_POST
def valider_absence(request, pk):
    if not request.user.est_rh:
        raise PermissionDenied
    absence = get_object_or_404(Absence, pk=pk)
    absence.valider(request.user, request.POST.get("commentaire", ""))
    log_activity(
        request.user,
        "Validation d'une absence",
        f"Absence de {absence.employe.nom_complet} validee.",
    )
    messages.success(request, "Absence validee.")
    return redirect("demandes:rh_absences")


@login_required
@require_POST
def rejeter_absence(request, pk):
    if not request.user.est_rh:
        raise PermissionDenied
    absence = get_object_or_404(Absence, pk=pk)
    absence.rejeter(request.user, request.POST.get("commentaire", ""))
    log_activity(
        request.user,
        "Refus d'une absence",
        f"Absence de {absence.employe.nom_complet} rejetee.",
    )
    messages.success(request, "Absence rejetee.")
    return redirect("demandes:rh_absences")


# ---------------------------------------------------------------------------
# Demission
# ---------------------------------------------------------------------------
class HistoriqueDemissionsView(AdminOuRHRequiredMixin, TemplateView):
    template_name = "demandes/historique_demissions.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["historique"] = _historique_par_mots_cles(
            "demission",
            "transmission d'une demission",
            "definition du preavis",
            "communication du preavis",
            "declaration de demission",
        )
        return ctx


class MaDemissionView(LoginRequiredMixin, TemplateView):
    """
    RG : la declaration de demission est irrevocable. Cette vue affiche la
    demission existante si elle existe, sinon propose le formulaire de declaration.
    """
    template_name = "demandes/ma_demission.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fiche = _fiche_employe_ou_403(self.request)
        ctx["demission"] = getattr(fiche, "demission", None)
        ctx["form"] = DemissionForm()
        return ctx

    def post(self, request, *args, **kwargs):
        fiche = _fiche_employe_ou_403(request)
        if getattr(fiche, "demission", None):
            messages.error(request, "Une demission a deja ete declaree ; elle est irrevocable.")
            return redirect("demandes:ma_demission")
        form = DemissionForm(request.POST)
        if form.is_valid():
            demission = form.save(commit=False)
            demission.employe = fiche
            demission.save()
            log_activity(
                request.user,
                "Declaration de demission",
                f"Demission de {fiche.nom_complet} declaree.",
            )
            messages.success(
                request,
                "Votre demission a ete enregistree. Elle est irrevocable. "
                "L'Administrateur va decider de la duree du preavis.",
            )
            return redirect("demandes:ma_demission")
        return self.render_to_response({"form": form, "demission": None})


class DemissionsATransmettreRHView(RoleRequiredMixin, ListView):
    """Etape 1 (RG-22) : demissions declarees, en attente de transmission a l'Admin."""
    roles_autorises = ["RH"]
    template_name = "demandes/rh_demissions_a_transmettre.html"
    context_object_name = "demissions"

    def get_queryset(self):
        return Demission.objects.filter(statut=StatutDemission.DECLAREE)


@login_required
@require_POST
def transmettre_demission(request, pk):
    if not request.user.est_rh:
        raise PermissionDenied
    demission = get_object_or_404(Demission, pk=pk, statut=StatutDemission.DECLAREE)
    demission.transmettre_a_admin(request.user)
    log_activity(
        request.user,
        "Transmission d'une demission RH",
        f"Demission de {demission.employe.nom_complet} transmise a l'Admin.",
    )
    messages.success(request, "Demission transmise a l'Administrateur pour determination du preavis.")
    return redirect("demandes:rh_demissions_a_transmettre")


class DemissionsAdminView(RoleRequiredMixin, ListView):
    roles_autorises = ["ADMIN"]
    template_name = "demandes/admin_demissions.html"
    context_object_name = "demissions"

    def get_queryset(self):
        return Demission.objects.filter(statut=StatutDemission.TRANSMISE_ADMIN)


@login_required
def definir_preavis(request, pk):
    if not request.user.est_admin:
        raise PermissionDenied
    demission = get_object_or_404(Demission, pk=pk, statut=StatutDemission.TRANSMISE_ADMIN)
    if request.method == "POST":
        form = PreavisForm(request.POST)
        if form.is_valid():
            demission.definir_preavis(
                request.user, form.cleaned_data["preavis_jours"], form.cleaned_data["commentaire"]
            )
            log_activity(
                request.user,
                "Definition du preavis",
                f"Preavis de {demission.employe.nom_complet} defini a {form.cleaned_data['preavis_jours']} jours.",
            )
            messages.success(request, "Preavis defini. Le Responsable RH va le communiquer a l'employe.")
            return redirect("demandes:admin_demissions")
    else:
        form = PreavisForm()
    return render(request, "demandes/definir_preavis.html", {"form": form, "demission": demission})


class DemissionsACommuniquerRHView(RoleRequiredMixin, ListView):
    """Etape 3 (RG-22) : preavis defini par l'Admin, a communiquer a l'employe."""
    roles_autorises = ["RH"]
    template_name = "demandes/rh_demissions_a_communiquer.html"
    context_object_name = "demissions"

    def get_queryset(self):
        return Demission.objects.filter(statut=StatutDemission.PREAVIS_DEFINI)


@login_required
@require_POST
def communiquer_demission(request, pk):
    if not request.user.est_rh:
        raise PermissionDenied
    demission = get_object_or_404(Demission, pk=pk, statut=StatutDemission.PREAVIS_DEFINI)
    demission.communiquer_a_employe()
    log_activity(
        request.user,
        "Communication du preavis",
        f"Preavis de {demission.employe.nom_complet} communique a l'employe.",
    )
    messages.success(request, "Decision communiquee a l'employe.")
    return redirect("demandes:rh_demissions_a_communiquer")
