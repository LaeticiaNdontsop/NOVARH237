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

from accounts.mixins import RoleRequiredMixin, droit_requis, exiger_droit
from notifications.models import ActivityLog, log_activity, notifier
from .forms import DemandeCongeForm, TraitementCommentaireForm, AbsenceForm, DemissionForm, PreavisForm
from .models import (
    DemandeConge, StatutDemande, DELAI_REAFFECTATION, choisir_utilisateur_disponible,
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
class HistoriqueCongesView(droit_requis("demandes"), TemplateView):
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


ONGLETS_STATUT = [
    ("", "Toutes"),
    ("attente", "En attente"),
    ("acceptees", "Acceptées"),
    ("refusees", "Refusées"),
]


def _filtre_statut(onglet):
    """Q correspondant a un onglet (statuts en attente / acceptees / refusees)."""
    if onglet == "attente":
        return Q(statut__in=[StatutDemande.EN_ATTENTE_RH, StatutDemande.EN_ATTENTE_ADMIN,
                             StatutDemande.APPROUVEE_A_NOTIFIER])
    if onglet == "acceptees":
        return Q(statut=StatutDemande.APPROUVEE)
    if onglet == "refusees":
        return Q(statut__in=[StatutDemande.REJETEE_RH, StatutDemande.REJETEE_ADMIN])
    return Q()


class MesDemandesCongeListView(LoginRequiredMixin, ListView):
    template_name = "demandes/mes_demandes.html"
    context_object_name = "demandes"
    paginate_by = 8

    def get_queryset(self):
        fiche = _fiche_employe_ou_403(self.request)
        return DemandeConge.objects.filter(employe=fiche).filter(_filtre_statut(self.request.GET.get("statut", "")))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["onglets"] = ONGLETS_STATUT
        ctx["onglet"] = self.request.GET.get("statut", "")
        return ctx


class CreerDemandeCongeView(LoginRequiredMixin, CreateView):
    model = DemandeConge
    form_class = DemandeCongeForm
    template_name = "demandes/demande_conge_form.html"
    success_url = reverse_lazy("demandes:mes_demandes")

    def form_valid(self, form):
        fiche = _fiche_employe_ou_403(self.request)
        user = self.request.user
        form.instance.employe = fiche
        if user.est_rh:
            # Un Responsable RH ne traite pas sa propre demande : elle va directement
            # a l'Administrateur, qui la voit immediatement dans ses demandes a decider.
            form.instance.statut = StatutDemande.EN_ATTENTE_ADMIN
            form.instance.admin_assigne = choisir_utilisateur_disponible("ADMIN")
            form.instance.date_limite_admin = timezone.now() + DELAI_REAFFECTATION
            form.instance.date_traitement_rh = timezone.now()
            form.instance.commentaire_rh = "Demande d'un Responsable RH : transmise directement a l'Administrateur."
        else:
            form.instance.rh_assigne = choisir_rh_disponible(exclure=user)
            form.instance.date_limite_rh = timezone.now() + DELAI_REAFFECTATION
        response = super().form_valid(form)
        demande = self.object

        if user.est_rh:
            destinataires = [demande.admin_assigne] if demande.admin_assigne else []
            message_info = "Votre demande a ete transmise directement a l'Administrateur."
        else:
            destinataires = [demande.rh_assigne] if demande.rh_assigne else []
            message_info = "Votre demande a ete soumise et transmise au Responsable RH."
        for destinataire in destinataires:
            notifier(user, destinataire,
                     f"Nouvelle demande {demande.reference} ({demande.get_type_demande_display()}) "
                     f"de {fiche.nom_complet} a traiter.")
        log_activity(
            user,
            "Soumission d'une demande",
            f"Demande de {demande.get_type_demande_display()} soumise pour {fiche.nom_complet}.",
        )
        messages.success(self.request, message_info)
        return response


class DetailDemandeCongeView(LoginRequiredMixin, DetailView):
    model = DemandeConge
    template_name = "demandes/demande_conge_detail.html"
    context_object_name = "demande"

    def get_object(self, queryset=None):
        demande = get_object_or_404(DemandeConge.objects.select_related("employe__utilisateur"), pk=self.kwargs["pk"])
        user = self.request.user
        if user.est_admin or user.est_rh or demande.employe.utilisateur_id == user.id:
            return demande
        raise PermissionDenied("Vous ne pouvez consulter que vos propres demandes.")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user, demande = self.request.user, self.object
        est_proprietaire = demande.employe.utilisateur_id == user.id
        ctx["est_proprietaire"] = est_proprietaire
        ctx["peut_transmettre"] = (
            user.est_rh and demande.statut == StatutDemande.EN_ATTENTE_RH and demande.rh_assigne_id == user.id
        )
        ctx["peut_communiquer"] = (
            user.est_rh and demande.statut == StatutDemande.APPROUVEE_A_NOTIFIER and demande.rh_assigne_id == user.id
        )
        ctx["peut_decider"] = (
            user.est_admin and demande.statut == StatutDemande.EN_ATTENTE_ADMIN
            and demande.admin_assigne_id in (user.id, None)
        )
        # L'employe voit le statut reel si le RH tarde a communiquer (5 h).
        ctx["couleur"] = demande.couleur_employe if est_proprietaire else demande.couleur
        ctx["statut_libelle"] = demande.statut_employe_display if est_proprietaire else demande.get_statut_display()
        return ctx


# ---------------------------------------------------------------------------
# Espace Responsable RH : traitement des conges/permissions (etapes 1 et 3)
# ---------------------------------------------------------------------------
class DemandesRHBaseView(droit_requis("demandes"), ListView):
    """Page « Demandes » du RH : KPI, filtres, tableau et acces au detail pour traiter."""
    template_name = "demandes/rh_demandes.html"
    context_object_name = "demandes"
    paginate_by = 10
    vue = "toutes"

    def get_queryset(self):
        reaffecter_demandes_expirees()
        user = self.request.user
        qs = DemandeConge.objects.select_related("employe__utilisateur").exclude(employe__utilisateur=user)
        if self.vue == "a_traiter":
            qs = qs.filter(statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=user)
        elif self.vue == "a_notifier":
            qs = qs.filter(statut=StatutDemande.APPROUVEE_A_NOTIFIER, rh_assigne=user)
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(Q(employe__utilisateur__last_name__icontains=recherche)
                           | Q(employe__utilisateur__first_name__icontains=recherche)
                           | Q(motif__icontains=recherche))
        type_demande = self.request.GET.get("type", "")
        if type_demande in ("CONGE", "PERMISSION"):
            qs = qs.filter(type_demande=type_demande)
        return qs.filter(_filtre_statut(self.request.GET.get("statut", "")))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tous = DemandeConge.objects.exclude(employe__utilisateur=self.request.user)
        ctx["vue"] = self.vue
        ctx["nb_attente"] = tous.filter(_filtre_statut("attente")).count()
        ctx["nb_acceptees"] = tous.filter(_filtre_statut("acceptees")).count()
        ctx["nb_refusees"] = tous.filter(_filtre_statut("refusees")).count()
        ctx["onglets"] = ONGLETS_STATUT
        ctx["onglet"] = self.request.GET.get("statut", "")
        ctx["recherche"] = self.request.GET.get("q", "")
        ctx["type_filtre"] = self.request.GET.get("type", "")
        return ctx


class DemandesRHView(DemandesRHBaseView):
    vue = "toutes"


class DemandesATraiterRHView(DemandesRHBaseView):
    """Etape 1 du circuit : demandes fraichement soumises, assignees a ce RH."""
    vue = "a_traiter"


class DemandesANotifierRHView(DemandesRHBaseView):
    """Etape 3 du circuit : demandes decidees par l'Admin, a cloturer/notifier."""
    vue = "a_notifier"


@login_required
@require_POST
def transmettre_a_admin(request, pk):
    exiger_droit(request.user, "demandes", "modification")
    demande = get_object_or_404(DemandeConge, pk=pk, statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=request.user)
    commentaire = request.POST.get("commentaire", "")
    demande.transmettre_a_admin(request.user, commentaire)
    if demande.admin_assigne:
        notifier(request.user, demande.admin_assigne,
                 f"Demande {demande.reference} ({demande.employe.nom_complet}) transmise pour decision.")
    log_activity(
        request.user,
        "Transmission d'une demande RH",
        f"Demande de {demande.get_type_demande_display()} transmise a l'Admin.",
    )
    messages.success(request, "Demande transmise à l'Administrateur pour décision.")
    return redirect("demandes:rh_demandes")


@login_required
@require_POST
def rejeter_par_rh(request, pk):
    exiger_droit(request.user, "demandes", "modification")
    demande = get_object_or_404(DemandeConge, pk=pk, statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=request.user)
    commentaire = request.POST.get("commentaire", "")
    demande.rejeter_par_rh(request.user, commentaire)
    notifier(request.user, demande.employe.utilisateur,
             f"Votre demande {demande.reference} a ete refusee. Motif : {commentaire or 'non precise'}.")
    log_activity(
        request.user,
        "Refus d'une demande RH",
        f"Demande de {demande.get_type_demande_display()} rejetee par le RH.",
    )
    messages.success(request, "Demande rejetée. L'employé sera informé du motif.")
    return redirect("demandes:rh_demandes")


@login_required
@require_POST
def cloturer_demande(request, pk):
    exiger_droit(request.user, "demandes", "modification")
    demande = get_object_or_404(
        DemandeConge, pk=pk, statut=StatutDemande.APPROUVEE_A_NOTIFIER, rh_assigne=request.user
    )
    demande.cloturer_par_rh()
    notifier(request.user, demande.employe.utilisateur,
             f"Votre demande {demande.reference} a ete approuvee.")
    log_activity(
        request.user,
        "Cloture d'une demande RH",
        f"Demande de {demande.get_type_demande_display()} cloturee et notifiee a l'employe.",
    )
    messages.success(request, "Demande clôturée : l'employé est notifié de l'approbation.")
    return redirect("demandes:rh_demandes")


# ---------------------------------------------------------------------------
# Espace Administrateur : decision finale sur les conges/permissions (etape 2)
# ---------------------------------------------------------------------------
class DemandesAdminView(RoleRequiredMixin, ListView):
    roles_autorises = ["ADMIN"]
    template_name = "demandes/admin_a_decider.html"
    context_object_name = "demandes"

    def get_queryset(self):
        reaffecter_demandes_expirees()
        user = self.request.user
        return DemandeConge.objects.select_related("employe__utilisateur").filter(
            statut=StatutDemande.EN_ATTENTE_ADMIN
        ).filter(Q(admin_assigne=user) | Q(admin_assigne__isnull=True))


def _demande_a_decider(request, pk):
    return get_object_or_404(
        DemandeConge.objects.filter(Q(admin_assigne=request.user) | Q(admin_assigne__isnull=True)),
        pk=pk, statut=StatutDemande.EN_ATTENTE_ADMIN,
    )


@login_required
@require_POST
def approuver_par_admin(request, pk):
    if not request.user.est_admin:
        raise PermissionDenied
    demande = _demande_a_decider(request, pk)
    commentaire = request.POST.get("commentaire", "")
    demande.approuver_par_admin(request.user, commentaire)
    if demande.statut == StatutDemande.APPROUVEE:
        notifier(request.user, demande.employe.utilisateur, f"Votre demande {demande.reference} a ete approuvee.")
    elif demande.rh_assigne:
        notifier(request.user, demande.rh_assigne,
                 f"La demande {demande.reference} ({demande.employe.nom_complet}) a ete approuvee : "
                 "merci de communiquer la decision a l'employe.")
    log_activity(
        request.user,
        "Approbation d'une demande admin",
        f"Demande de {demande.get_type_demande_display()} approuvee par l'Admin.",
    )
    messages.success(request, "Demande approuvée.")
    return redirect("demandes:admin_a_decider")


@login_required
@require_POST
def rejeter_par_admin(request, pk):
    if not request.user.est_admin:
        raise PermissionDenied
    demande = _demande_a_decider(request, pk)
    commentaire = request.POST.get("commentaire", "")
    demande.rejeter_par_admin(request.user, commentaire)
    notifier(request.user, demande.employe.utilisateur,
             f"Votre demande {demande.reference} a ete refusee. Motif : {commentaire or 'non precise'}.")
    log_activity(
        request.user,
        "Refus d'une demande admin",
        f"Demande de {demande.get_type_demande_display()} rejetee par l'Admin.",
    )
    messages.success(request, "Demande rejetée.")
    return redirect("demandes:admin_a_decider")


# ---------------------------------------------------------------------------
# Absences
# ---------------------------------------------------------------------------
class HistoriqueAbsencesView(droit_requis("absences"), TemplateView):
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
    paginate_by = 8

    def get_queryset(self):
        fiche = _fiche_employe_ou_403(self.request)
        return Absence.objects.filter(employe=fiche)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fiche = _fiche_employe_ou_403(self.request)
        annee = timezone.localdate().year
        toutes = Absence.objects.filter(employe=fiche)
        ctx["nb_validees_annee"] = toutes.filter(statut=StatutAbsence.APPROUVEE, date_debut__year=annee).count()
        ctx["nb_en_attente"] = toutes.filter(statut=StatutAbsence.EN_ATTENTE).count()
        ctx["nb_total"] = toutes.count()
        return ctx


def _destinataires_validation_absence(employe):
    """Un employe : les RH (sauf lui). Un RH : les Administrateurs."""
    from accounts.models import Utilisateur

    if employe.utilisateur.est_rh:
        return list(Utilisateur.objects.filter(role="ADMIN", is_active=True))
    return list(Utilisateur.objects.filter(role="RH", is_active=True).exclude(pk=employe.utilisateur_id))


def _absences_traitables(user):
    """Absences qu'un utilisateur peut valider/refuser (jamais les siennes)."""
    qs = Absence.objects.select_related("employe__utilisateur").exclude(employe__utilisateur=user)
    if user.est_admin:
        return qs.filter(employe__utilisateur__role="RH")
    return qs


class CreerAbsenceView(LoginRequiredMixin, CreateView):
    model = Absence
    form_class = AbsenceForm
    template_name = "demandes/absence_form.html"
    success_url = reverse_lazy("demandes:mes_absences")

    def form_valid(self, form):
        fiche = _fiche_employe_ou_403(self.request)
        form.instance.employe = fiche
        response = super().form_valid(form)
        for destinataire in _destinataires_validation_absence(fiche):
            notifier(self.request.user, destinataire,
                     f"Absence a valider : {fiche.nom_complet} du {form.instance.date_debut:%d/%m/%Y} "
                     f"au {form.instance.date_fin:%d/%m/%Y}.")
        log_activity(
            self.request.user,
            "Declaration d'une absence",
            f"Absence declaree pour {fiche.nom_complet} du {form.instance.date_debut} au {form.instance.date_fin}.",
        )
        messages.success(self.request, "Absence déclarée, en attente de validation.")
        return response


class AbsencesRHView(droit_requis("absences"), ListView):
    """Suivi des absences : le RH valide celles des employes, l'Administrateur celles des RH."""
    template_name = "demandes/rh_absences.html"
    context_object_name = "absences"
    paginate_by = 10

    def get_queryset(self):
        qs = _absences_traitables(self.request.user)
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(Q(employe__utilisateur__last_name__icontains=recherche)
                           | Q(employe__utilisateur__first_name__icontains=recherche)
                           | Q(motif__icontains=recherche))
        statut = self.request.GET.get("statut", "")
        if statut in dict(StatutAbsence.choices):
            qs = qs.filter(statut=statut)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = _absences_traitables(self.request.user)
        aujourdhui = timezone.localdate()
        ctx["nb_en_cours"] = base.filter(statut=StatutAbsence.APPROUVEE, date_debut__lte=aujourdhui,
                                         date_fin__gte=aujourdhui).count()
        ctx["nb_a_valider"] = base.filter(statut=StatutAbsence.EN_ATTENTE).count()
        ctx["nb_total"] = base.count()
        ctx["statuts"] = StatutAbsence.choices
        ctx["recherche"] = self.request.GET.get("q", "")
        ctx["statut_filtre"] = self.request.GET.get("statut", "")
        return ctx


def _traiter_absence(request, pk, validation):
    exiger_droit(request.user, "absences", "modification")
    absence = get_object_or_404(_absences_traitables(request.user), pk=pk)
    commentaire = request.POST.get("commentaire", "")
    if validation:
        absence.valider(request.user, commentaire)
        verbe, message = "Validation", "validée"
    else:
        absence.rejeter(request.user, commentaire)
        verbe, message = "Refus", "rejetée"
    notifier(request.user, absence.employe.utilisateur,
             f"Votre absence du {absence.date_debut:%d/%m/%Y} au {absence.date_fin:%d/%m/%Y} a ete "
             f"{'validee' if validation else 'refusee'}.")
    log_activity(
        request.user,
        f"{verbe} d'une absence",
        f"Absence de {absence.employe.nom_complet} {'validee' if validation else 'rejetee'}.",
    )
    messages.success(request, f"Absence {message}.")
    return redirect("demandes:rh_absences")


@login_required
@require_POST
def valider_absence(request, pk):
    return _traiter_absence(request, pk, True)


@login_required
@require_POST
def rejeter_absence(request, pk):
    return _traiter_absence(request, pk, False)


# ---------------------------------------------------------------------------
# Demission
# ---------------------------------------------------------------------------
class HistoriqueDemissionsView(droit_requis("demissions"), TemplateView):
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


class DemissionsATransmettreRHView(droit_requis("demissions"), ListView):
    """Etape 1 (RG-22) : demissions declarees, en attente de transmission a l'Admin."""
    template_name = "demandes/rh_demissions_a_transmettre.html"
    context_object_name = "demissions"

    def get_queryset(self):
        return Demission.objects.filter(statut=StatutDemission.DECLAREE).exclude(
            employe__utilisateur=self.request.user
        )


@login_required
@require_POST
def transmettre_demission(request, pk):
    exiger_droit(request.user, "demissions", "modification")
    demission = get_object_or_404(
        Demission.objects.exclude(employe__utilisateur=request.user), pk=pk, statut=StatutDemission.DECLAREE
    )
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


class DemissionsACommuniquerRHView(droit_requis("demissions"), ListView):
    """Etape 3 (RG-22) : preavis defini par l'Admin, a communiquer a l'employe."""
    template_name = "demandes/rh_demissions_a_communiquer.html"
    context_object_name = "demissions"

    def get_queryset(self):
        return Demission.objects.filter(statut=StatutDemission.PREAVIS_DEFINI).exclude(
            employe__utilisateur=self.request.user
        )


@login_required
@require_POST
def communiquer_demission(request, pk):
    exiger_droit(request.user, "demissions", "modification")
    demission = get_object_or_404(
        Demission.objects.exclude(employe__utilisateur=request.user), pk=pk, statut=StatutDemission.PREAVIS_DEFINI
    )
    demission.communiquer_a_employe()
    log_activity(
        request.user,
        "Communication du preavis",
        f"Preavis de {demission.employe.nom_complet} communique a l'employe.",
    )
    messages.success(request, "Decision communiquee a l'employe.")
    return redirect("demandes:rh_demissions_a_communiquer")
