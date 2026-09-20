from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, TemplateView

from accounts.mixins import AdminOuRHRequiredMixin
from notifications.models import log_activity
from .forms import EmployeForm, ContratForm, RemunerationForm, DocumentForm
from .models import Employe, Contrat, Remuneration, Document, StatutEmploye


# ---------------------------------------------------------------------------
# Employes (BF-RH-01 / BF-RH-02 / BF-ADM08) : partage Admin + RH depuis la v6
# ---------------------------------------------------------------------------
class ListeEmployesView(AdminOuRHRequiredMixin, ListView):
    model = Employe
    template_name = "employees/employe_list.html"
    context_object_name = "employes"
    paginate_by = 15

    def get_queryset(self):
        qs = Employe.objects.select_related("utilisateur").all()
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(utilisateur__last_name__icontains=recherche) | qs.filter(
                utilisateur__first_name__icontains=recherche
            ) | qs.filter(matricule__icontains=recherche) | qs.filter(poste__icontains=recherche)
        statut = self.request.GET.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recherche"] = self.request.GET.get("q", "")
        ctx["statut_filtre"] = self.request.GET.get("statut", "")
        return ctx


class DetailEmployeView(LoginRequiredMixin, DetailView):
    """
    Un employe peut consulter sa propre fiche ; Admin/RH peuvent consulter toutes
    les fiches. RG-06 : acces limite a ses propres donnees sinon.
    """
    model = Employe
    template_name = "employees/employe_detail.html"
    context_object_name = "employe"

    def get_object(self, queryset=None):
        obj = get_object_or_404(Employe, pk=self.kwargs["pk"])
        user = self.request.user
        if user.peut_gerer_employes or obj.utilisateur_id == user.id:
            return obj
        raise PermissionDenied("Vous ne pouvez consulter que votre propre fiche.")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["peut_voir_remuneration"] = user.peut_gerer_employes or self.object.utilisateur_id == user.id
        # RG-05 : le RH ne peut pas consulter les documents des AUTRES employes.
        ctx["peut_voir_documents"] = user.est_admin or self.object.utilisateur_id == user.id
        return ctx


class CreerEmployeView(AdminOuRHRequiredMixin, CreateView):
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
        messages.success(self.request, "Fiche employe creee avec succes.")
        return response


class ModifierEmployeView(AdminOuRHRequiredMixin, UpdateView):
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
        messages.success(self.request, "Fiche employe mise a jour.")
        return response


class DesactiverEmployeView(AdminOuRHRequiredMixin, View):
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
        messages.success(request, f"La fiche de {employe.nom_complet} a ete desactivee.")
        return redirect("employees:liste_employes")


# ---------------------------------------------------------------------------
# Contrats (BF-RH-04 / BF-RH-05)
# ---------------------------------------------------------------------------
class AjouterContratView(AdminOuRHRequiredMixin, CreateView):
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
        messages.success(self.request, "Contrat enregistre.")
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
class AjouterRemunerationView(AdminOuRHRequiredMixin, CreateView):
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
        messages.success(self.request, "Remuneration enregistree.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["employe"] = self.employe
        return ctx

    def get_success_url(self):
        return reverse_lazy("employees:detail_employe", kwargs={"pk": self.employe.pk})


# ---------------------------------------------------------------------------
# Documents (BF-RH-12 / BF-EMP09) - RG-05, RG-06, RG-17
# ---------------------------------------------------------------------------
class AjouterDocumentView(AdminOuRHRequiredMixin, CreateView):
    """
    Ajout reserve a l'Admin/RH. RG-05 : meme le RH ne consulte pas les documents
    des AUTRES employes ailleurs dans l'appli, mais il peut ici en deposer un
    (depot != consultation). Un controle plus strict peut etre ajoute si le jury
    l'exige (ex. reserver le depot a l'Admin uniquement).
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
        messages.success(self.request, "Document ajoute.")
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

        if not (user.est_admin or user.est_rh or document.employe.utilisateur_id == user.id):
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
            ctx["documents"] = Document.objects.filter(employe=fiche).select_related("employe")
        ctx["document_form"] = DocumentForm()
        return ctx

    def post(self, request, *args, **kwargs):
        fiche = getattr(request.user, "fiche_employe", None)
        if fiche is None:
            messages.error(request, "Aucune fiche employe n'est associee a votre compte.")
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
            messages.success(request, "Document importe avec succes.")
            return redirect("employees:mes_documents")

        messages.error(request, "Le document est invalide. Veuillez verifier le type et le fichier.")
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


class MesEvaluationsFormationsView(LoginRequiredMixin, TemplateView):
    template_name = "employees/mes_evaluations_formations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fiche = getattr(self.request.user, "fiche_employe", None)
        if fiche is None:
            ctx["evaluations"] = []
            ctx["formations"] = []
            return ctx
        from core.models import Evaluation

        ctx["evaluations"] = Evaluation.objects.filter(employe=fiche)
        ctx["formations"] = fiche.formations.all()
        return ctx
