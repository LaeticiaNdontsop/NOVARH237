from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, TemplateView

from accounts.mixins import droit_requis
from notifications.models import log_activity
from .forms import EmployeForm, ContratForm, RemunerationForm, DocumentForm
from .models import Employe, Contrat, Remuneration, Document, StatutEmploye, TypeContrat


# ---------------------------------------------------------------------------
# Employes (BF-RH-01 / BF-RH-02 / BF-ADM08) : partage Admin + RH depuis la v6
# ---------------------------------------------------------------------------
class ListeEmployesView(droit_requis("employes"), ListView):
    model = Employe
    template_name = "employees/employe_list.html"
    context_object_name = "employes"

    def get_paginate_by(self, queryset):
        par_page = self.request.GET.get("par_page", "10")
        return int(par_page) if par_page in ("10", "25", "50") else 10

    def get_queryset(self):
        qs = Employe.objects.select_related("utilisateur").prefetch_related("contrats")
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(
                Q(utilisateur__last_name__icontains=recherche) | Q(utilisateur__first_name__icontains=recherche)
                | Q(matricule__icontains=recherche) | Q(poste__icontains=recherche)
            )
        departement = self.request.GET.get("departement", "")
        if departement:
            qs = qs.filter(service=departement)
        contrat = self.request.GET.get("contrat", "")
        if contrat in dict(TypeContrat.choices):
            qs = qs.filter(contrats__type_contrat=contrat)
        statut = self.request.GET.get("statut")
        if statut in dict(StatutEmploye.choices):
            qs = qs.filter(statut=statut)
        return qs.distinct().order_by("matricule")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        get = self.request.GET
        ctx.update({
            "recherche": get.get("q", ""),
            "departement_filtre": get.get("departement", ""),
            "contrat_filtre": get.get("contrat", ""),
            "statut_filtre": get.get("statut", ""),
            "par_page": get.get("par_page", "10"),
            "departements": Employe.objects.exclude(service="").values_list("service", flat=True)
            .distinct().order_by("service"),
            "types_contrat": TypeContrat.choices,
            "statuts": StatutEmploye.choices,
            "total": Employe.objects.count(),
            "peut_creer": self.request.user.a_droit("employes", "creation"),
            "peut_modifier": self.request.user.a_droit("employes", "modification"),
            "peut_desactiver": self.request.user.a_droit("employes", "suppression"),
        })
        return ctx


ONGLETS_FICHE = [("informations", "Informations"), ("demandes", "Demandes"), ("absences", "Absences"),
                 ("documents", "Documents")]


class DetailEmployeView(LoginRequiredMixin, DetailView):
    """
    Un employe peut consulter sa propre fiche ; les utilisateurs ayant le droit
    « Employes » consultent toutes les fiches (RG-06 : acces limite sinon).
    """
    model = Employe
    template_name = "employees/employe_detail.html"
    context_object_name = "employe"

    def get_object(self, queryset=None):
        obj = get_object_or_404(Employe.objects.select_related("utilisateur", "manager__utilisateur"),
                                pk=self.kwargs["pk"])
        user = self.request.user
        if user.a_droit("employes", "lecture") or obj.utilisateur_id == user.id:
            return obj
        raise PermissionDenied("Vous ne pouvez consulter que votre propre fiche.")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user, employe = self.request.user, self.object
        est_proprietaire = employe.utilisateur_id == user.id
        gestionnaire = user.a_droit("employes", "lecture")
        # RG-05 : le RH ne consulte pas les documents des AUTRES employes.
        peut_voir_documents = user.est_admin or est_proprietaire
        peut_voir_remuneration = est_proprietaire or user.a_droit("remunerations", "lecture")
        onglets = [o for o in ONGLETS_FICHE if o[0] != "documents" or peut_voir_documents]
        onglet = self.request.GET.get("onglet", "informations")
        if onglet not in dict(onglets):
            onglet = "informations"
        ctx.update({
            "peut_voir_documents": peut_voir_documents,
            "peut_voir_remuneration": peut_voir_remuneration,
            "peut_gerer": gestionnaire and user.a_droit("employes", "modification"),
            "peut_desactiver": user.a_droit("employes", "suppression"),
            "peut_ajouter_remuneration": user.a_droit("remunerations", "creation"),
            "onglets": onglets,
            "onglet": onglet,
            "contrat": employe.contrat_actuel,
            "remuneration": employe.remunerations.first() if peut_voir_remuneration else None,
            "demandes": employe.demandes_conge.all()[:10],
            "absences": employe.absences.all()[:10],
            "nb_demandes": employe.demandes_conge.count(),
            "nb_absences": employe.absences.count(),
        })
        return ctx


class CreerEmployeView(droit_requis("employes", "creation", "creation"), CreateView):
    model = Employe
    form_class = EmployeForm
    template_name = "employees/employe_form.html"
    success_url = reverse_lazy("employees:liste_employes")

    def form_valid(self, form):
        form.instance.cree_par = self.request.user
        response = super().form_valid(form)
        Contrat.objects.get_or_create(
            employe=self.object,
            defaults={
                "type_contrat": "CDI",
                "poste": self.object.poste,
                "service": self.object.service,
                "salaire": 0,
                "date_debut": self.object.date_embauche,
            },
        )
        log_activity(
            self.request.user,
            "Creation d'une fiche employe",
            f"Fiche employe {self.object.matricule} creee pour {self.object.nom_complet}.",
        )
        messages.success(self.request, "Fiche employé créée avec succès.")
        return response


class ModifierEmployeView(droit_requis("employes", "modification", "modification"), UpdateView):
    model = Employe
    form_class = EmployeForm
    template_name = "employees/employe_form.html"
    success_url = reverse_lazy("employees:liste_employes")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Modification d'une fiche employe",
            f"Fiche employe {self.object.matricule} mise a jour.",
        )
        messages.success(self.request, "Fiche employé mise à jour.")
        return response


class DesactiverEmployeView(droit_requis("employes", "suppression", "suppression"), View):
    """BF-ADM08 / BF-RH-01 : desactivation (pas de suppression physique, tracabilite RG-13)."""

    def post(self, request, pk):
        employe = get_object_or_404(Employe, pk=pk)
        employe.statut = StatutEmploye.INACTIF
        employe.date_desactivation = timezone.now()
        employe.save(update_fields=["statut", "date_desactivation"])
        log_activity(
            request.user,
            "Desactivation d'une fiche employe",
            f"Fiche employe {employe.matricule} desactivee.",
        )
        messages.success(request, f"La fiche de {employe.nom_complet} a été désactivée.")
        return redirect("employees:liste_employes")


# ---------------------------------------------------------------------------
# Contrats (BF-RH-04 / BF-RH-05)
# ---------------------------------------------------------------------------
class AjouterContratView(droit_requis("employes", "modification", "modification"), CreateView):
    model = Contrat
    form_class = ContratForm
    template_name = "employees/contrat_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.employe = get_object_or_404(Employe, pk=kwargs["employe_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.employe = self.employe
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Enregistrement d'un contrat",
            f"Contrat pour {self.employe.nom_complet} enregistre.",
        )
        messages.success(self.request, "Contrat enregistré.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["employe"] = self.employe
        return ctx

    def get_success_url(self):
        return reverse_lazy("employees:detail_employe", kwargs={"pk": self.employe.pk})


# ---------------------------------------------------------------------------
# Remunerations (BF-RH-06) - donnee confidentielle, RG-12
# ---------------------------------------------------------------------------
class AjouterRemunerationView(droit_requis("remunerations", "creation", "creation"), CreateView):
    model = Remuneration
    form_class = RemunerationForm
    template_name = "employees/remuneration_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.employe = get_object_or_404(Employe, pk=kwargs["employe_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.employe = self.employe
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Enregistrement d'une remuneration",
            f"Remuneration pour {self.employe.nom_complet} enregistree.",
        )
        messages.success(self.request, "Rémunération enregistrée.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["employe"] = self.employe
        return ctx

    def get_success_url(self):
        return reverse_lazy("employees:detail_employe", kwargs={"pk": self.employe.pk})


class ListeRemunerationsView(droit_requis("remunerations"), ListView):
    """
    Page Remunerations : montants MASQUES par defaut ; l'affichage des donnees d'un
    employe est une action explicite (POST) enregistree dans le journal (RG-12 / RG-13).
    """
    model = Employe
    template_name = "employees/remunerations_liste.html"
    context_object_name = "employes"
    paginate_by = 10

    def get_queryset(self):
        qs = Employe.objects.select_related("utilisateur").prefetch_related("contrats", "remunerations")
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(Q(utilisateur__last_name__icontains=recherche)
                           | Q(utilisateur__first_name__icontains=recherche) | Q(matricule__icontains=recherche))
        departement = self.request.GET.get("departement", "")
        if departement:
            qs = qs.filter(service=departement)
        contrat = self.request.GET.get("contrat", "")
        if contrat in dict(TypeContrat.choices):
            qs = qs.filter(contrats__type_contrat=contrat)
        return qs.distinct().order_by("matricule")

    def _selection(self):
        pk = self.request.GET.get("employe") or self.request.POST.get("employe")
        if pk and str(pk).isdigit():
            return Employe.objects.select_related("utilisateur").filter(pk=int(pk)).first()
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        selection = self._selection()
        ctx.update({
            "recherche": self.request.GET.get("q", ""),
            "departement_filtre": self.request.GET.get("departement", ""),
            "contrat_filtre": self.request.GET.get("contrat", ""),
            "departements": Employe.objects.exclude(service="").values_list("service", flat=True)
            .distinct().order_by("service"),
            "types_contrat": TypeContrat.choices,
            "selection": selection,
            "donnees_visibles": kwargs.get("donnees_visibles", False),
            "remuneration": selection.remunerations.first() if selection and kwargs.get("donnees_visibles") else None,
            "peut_ajouter": self.request.user.a_droit("remunerations", "creation"),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        selection = self._selection()
        if selection is None:
            return redirect("employees:liste_remunerations")
        log_activity(request.user, "Consultation de remuneration",
                     f"Donnees de remuneration de {selection.nom_complet} affichees.")
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data(donnees_visibles=True))


# ---------------------------------------------------------------------------
# Documents (BF-RH-12 / BF-EMP09) - RG-05, RG-06, RG-17
# ---------------------------------------------------------------------------
class AjouterDocumentView(droit_requis("employes", "modification", "modification"), CreateView):
    """
    Depot reserve aux gestionnaires. RG-05 : le RH ne consulte pas les documents
    des AUTRES employes ailleurs dans l'appli, mais il peut ici en deposer un.
    """
    model = Document
    form_class = DocumentForm
    template_name = "employees/document_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.employe = get_object_or_404(Employe, pk=kwargs["employe_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.employe = self.employe
        form.instance.ajoute_par = self.request.user
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Ajout d'un document",
            f"Document {self.object.get_type_document_display()} ajoute pour {self.employe.nom_complet}.",
        )
        messages.success(self.request, "Document ajouté.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["employe"] = self.employe
        return ctx

    def get_success_url(self):
        return reverse_lazy("employees:detail_employe", kwargs={"pk": self.employe.pk})


class DocumentDetailView(LoginRequiredMixin, TemplateView):
    template_name = "employees/document_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        document = get_object_or_404(Document, pk=self.kwargs["pk"])
        user = self.request.user

        # RG-05 : le RH ne consulte pas les documents des AUTRES employes.
        if not (user.est_admin or document.employe.utilisateur_id == user.id):
            raise PermissionDenied("Vous ne pouvez pas consulter ce document.")

        ctx["document"] = document
        ctx["contrat"] = document.employe.contrats.order_by("-date_debut").first() if document.type_document == "CONTRAT" else None
        return ctx


class MesDocumentsView(LoginRequiredMixin, TemplateView):
    template_name = "employees/mes_documents.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fiche = getattr(self.request.user, "fiche_employe", None)
        if fiche is None:
            ctx["documents"] = []
        else:
            contrat = fiche.contrats.order_by("-date_debut").first()
            if contrat:
                document_contrat, _ = Document.objects.get_or_create(
                    employe=fiche,
                    type_document="CONTRAT",
                )
                if contrat.fichier_contrat:
                    document_contrat.fichier = contrat.fichier_contrat
                document_contrat.ajoute_par = fiche.utilisateur
                document_contrat.save()
            documents = Document.objects.filter(employe=fiche).select_related("employe")
            recherche = self.request.GET.get("q", "").strip().lower()
            type_doc = self.request.GET.get("type", "")
            documents = [
                d for d in documents
                if (not type_doc or d.type_document == type_doc)
                and (not recherche or recherche in d.get_type_document_display().lower())
            ]
            ctx["documents"] = documents
        from .models import TypeDocument
        ctx["types_document"] = TypeDocument.choices
        ctx["recherche"] = self.request.GET.get("q", "")
        ctx["type_filtre"] = self.request.GET.get("type", "")
        ctx["document_form"] = DocumentForm()
        return ctx

    def post(self, request, *args, **kwargs):
        fiche = getattr(request.user, "fiche_employe", None)
        if fiche is None:
            messages.error(request, "Aucune fiche employé n'est associée à votre compte.")
            return redirect("employees:mes_documents")

        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.employe = fiche
            document.ajoute_par = request.user
            document.save()
            log_activity(
                request.user,
                "Import d'un document personnel",
                f"Document {document.get_type_document_display()} importe pour {fiche.nom_complet}.",
            )
            messages.success(request, "Document importé avec succès.")
            return redirect("employees:mes_documents")

        messages.error(request, "Le document est invalide. Vérifiez le type et le fichier.")
        return redirect("employees:mes_documents")


class MesRemunerationsView(LoginRequiredMixin, ListView):
    model = Remuneration
    template_name = "employees/mes_remunerations.html"
    context_object_name = "remunerations"

    def get_queryset(self):
        fiche = getattr(self.request.user, "fiche_employe", None)
        if fiche is None:
            return Remuneration.objects.none()
        return Remuneration.objects.filter(employe=fiche).select_related("employe")


class MesFormationsView(LoginRequiredMixin, TemplateView):
    """BF-EMP10 / RG-23 : uniquement les formations pour lesquelles l'employe a ete cible."""
    template_name = "employees/mes_formations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fiche = getattr(self.request.user, "fiche_employe", None)
        ctx["participations"] = (
            fiche.participations_formations.select_related("formation") if fiche is not None else []
        )
        return ctx
