"""Offres d'emploi (BF-RH-15) et Recrutement (BF-RH-16, RG-10, RG-11)."""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from accounts.mixins import droit_requis, exiger_droit
from notifications.models import ActivityLog, log_activity
from .forms import CandidatureForm, OffreForm
from .models import (
    ETAPES_RECRUTEMENT, Candidature, Offre, StatutCandidature, StatutOffre,
)


class HistoriqueRecrutementsView(droit_requis("recrutements"), TemplateView):
    template_name = "core/historique_recrutements.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filtre = Q(action__icontains="candidat") | Q(details__icontains="candidat")
        filtre |= Q(action__icontains="offre") | Q(details__icontains="offre")
        filtre |= Q(action__icontains="recrut") | Q(details__icontains="recrut")
        ctx["historique"] = ActivityLog.objects.filter(filtre).order_by("-date_creation")[:200]
        return ctx


def _filtrer_offres(offres, request):
    departement = request.GET.get("departement", "")
    etape = request.GET.get("etape", "")
    statut = request.GET.get("statut", "")
    recherche = request.GET.get("q", "").strip().lower()

    def statut_ok(offre):
        if not statut:
            return True
        if statut == "EXPIREE":
            return offre.est_expiree
        return offre.statut == statut and not (statut == "PUBLIEE" and offre.est_expiree)

    return [
        o for o in offres
        if (not departement or o.departement == departement)
        and (not etape or o.etape == etape)
        and statut_ok(o)
        and (not recherche or recherche in o.poste.lower() or recherche in o.description.lower()
             or recherche in o.competences.lower())
    ]


STATUTS_OFFRE_FILTRE = [
    ("BROUILLON", "Brouillon"), ("PUBLIEE", "Publiée"), ("EXPIREE", "Expirée"),
    ("POURVUE", "Pourvue"), ("FERMEE", "Fermée"),
]


class RecrutementsView(droit_requis("recrutements"), TemplateView):
    """Suivi des recrutements : compteurs, filtres, tableau par offre."""
    template_name = "core/recrutements.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        toutes = list(Offre.objects.select_related("responsable").prefetch_related("candidatures"))
        ctx.update({
            "offres": _filtrer_offres(toutes, self.request),
            "nb_recrutements_en_cours": sum(1 for o in toutes if o.est_active),
            "nb_candidatures": sum(o.nombre_candidatures for o in toutes),
            "nb_entretiens": sum(o.entretiens_planifies for o in toutes),
            "nb_recrutes": sum(o.nombre_recrutes for o in toutes),
            "departements": sorted({o.departement for o in toutes if o.departement}),
            "etapes": ETAPES_RECRUTEMENT,
            "statuts": STATUTS_OFFRE_FILTRE,
            "filtre_departement": self.request.GET.get("departement", ""),
            "filtre_etape": self.request.GET.get("etape", ""),
            "filtre_statut": self.request.GET.get("statut", ""),
            "recherche": self.request.GET.get("q", ""),
            "recrutes": Candidature.objects.filter(recrute=True).select_related("offre"),
        })
        return ctx


class OffresView(droit_requis("recrutements"), TemplateView):
    template_name = "core/offres.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        toutes = list(Offre.objects.select_related("responsable").prefetch_related("candidatures"))
        ctx.update({
            "offres": _filtrer_offres(toutes, self.request),
            "nb_actives": sum(1 for o in toutes if o.est_active),
            "nb_total": len(toutes),
            "texte_total": f"Sur {len(toutes)} offre(s) au total",
            "departements": sorted({o.departement for o in toutes if o.departement}),
            "statuts": STATUTS_OFFRE_FILTRE,
            "filtre_departement": self.request.GET.get("departement", ""),
            "filtre_statut": self.request.GET.get("statut", ""),
            "recherche": self.request.GET.get("q", ""),
        })
        return ctx


def _statut_depuis_bouton(request, form):
    action = request.POST.get("action")
    if action == "publier":
        form.instance.statut = StatutOffre.PUBLIEE
        if not form.instance.date_publication:
            form.instance.date_publication = timezone.localdate()
    elif action == "brouillon":
        form.instance.statut = StatutOffre.BROUILLON


class CreerOffreView(droit_requis("recrutements", "creation", "creation"), CreateView):
    model = Offre
    form_class = OffreForm
    template_name = "core/offre_form.html"
    success_url = reverse_lazy("core:offres")

    def get_initial(self):
        initial = super().get_initial()
        initial["responsable"] = self.request.user.pk
        return initial

    def form_valid(self, form):
        form.instance.creee_par = self.request.user
        _statut_depuis_bouton(self.request, form)
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Creation d'une offre",
            f"Offre {form.instance.poste} enregistree ({form.instance.get_statut_display()}).",
        )
        messages.success(self.request, "Offre enregistrée.")
        return response


class ModifierOffreView(droit_requis("recrutements"), UpdateView):
    model = Offre
    form_class = OffreForm
    template_name = "core/offre_form.html"
    success_url = reverse_lazy("core:offres")

    def form_valid(self, form):
        _statut_depuis_bouton(self.request, form)
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Modification d'une offre",
            f"Offre {form.instance.poste} modifiee.",
        )
        messages.success(self.request, "Offre mise à jour.")
        return response


class SupprimerOffreView(droit_requis("recrutements", "lecture", "suppression"), View):
    """Suppression avec confirmation ; les candidatures rattachees sont supprimees avec l'offre."""
    template_name = "core/offre_confirm_delete.html"

    def get(self, request, pk):
        offre = get_object_or_404(Offre, pk=pk)
        return render(request, self.template_name, {"offre": offre, "nb_candidatures": offre.candidatures.count()})

    def post(self, request, pk):
        offre = get_object_or_404(Offre, pk=pk)
        poste = offre.poste
        offre.delete()
        log_activity(request.user, "Suppression d'une offre", f"Offre {poste} supprimee.")
        messages.success(request, "Offre supprimée.")
        return redirect("core:offres")


class CandidaturesOffreView(droit_requis("recrutements"), TemplateView):
    """Suivi des candidatures d'une offre."""
    template_name = "core/candidatures_offre.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        offre = get_object_or_404(Offre.objects.prefetch_related("candidatures"), pk=self.kwargs["pk"])
        candidatures = list(offre.candidatures.all())
        statut = self.request.GET.get("statut", "")
        recherche = self.request.GET.get("q", "").strip().lower()
        filtrees = [
            c for c in candidatures
            if (not statut or c.statut == statut)
            and (not recherche or recherche in c.nom_candidat.lower() or recherche in c.email.lower()
                 or recherche in c.telephone.lower())
        ]
        ctx.update({
            "offre": offre,
            "candidatures": filtrees,
            "nb_total": len(candidatures),
            "statuts": StatutCandidature.choices,
            "statut_filtre": statut,
            "recherche": self.request.GET.get("q", ""),
        })
        return ctx


class AjouterCandidatureView(droit_requis("recrutements", "creation", "creation"), CreateView):
    """RG-11 : le RH importe manuellement la candidature ; le candidat n'a pas de compte."""
    model = Candidature
    form_class = CandidatureForm
    template_name = "core/candidature_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.offre = get_object_or_404(Offre, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.offre = form.cleaned_data["offre"]
        form.instance.saisie_par = self.request.user
        if form.cleaned_data["statut"] == StatutCandidature.RETENUE:
            form.instance.recrute = True
            form.instance.date_recrutement = timezone.now()
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Enregistrement d'une candidature",
            f"Candidature de {self.object.nom_candidat} enregistree pour l'offre {self.offre.poste}.",
        )
        messages.success(self.request, "Candidature enregistrée.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["offre"] = self.offre
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        initial["offre"] = self.offre.pk
        return initial

    def get_success_url(self):
        return reverse_lazy("core:candidatures_offre", kwargs={"pk": self.offre.pk})


class DetailCandidatureView(droit_requis("recrutements"), DetailView):
    model = Candidature
    template_name = "core/candidature_detail.html"
    context_object_name = "candidature"

    def get_queryset(self):
        return Candidature.objects.select_related("offre__responsable", "saisie_par")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = self.object
        decision = c.statut in (StatutCandidature.RETENUE, StatutCandidature.REJETEE) or c.recrute
        ctx["etapes"] = [
            {"libelle": "Candidature reçue", "date": c.date_candidature, "fait": True},
            {"libelle": "À analyser", "date": c.date_candidature,
             "fait": True, "courante": c.statut == StatutCandidature.RECUE},
            {"libelle": "Entretien RH", "date": c.date_entretien, "fait": bool(c.date_entretien),
             "courante": c.statut == StatutCandidature.ENTRETIEN and not c.date_entretien_technique},
            {"libelle": "Entretien technique", "date": c.date_entretien_technique,
             "fait": bool(c.date_entretien_technique)},
            {"libelle": "Décision finale", "date": c.date_recrutement, "fait": decision,
             "detail": "Recruté(e)" if c.recrute else c.get_statut_display() if decision else ""},
        ]
        ctx["statuts"] = StatutCandidature
        return ctx


def _lire_date(request, champ):
    valeur = request.POST.get(champ)
    if not valeur:
        return None, True
    date = parse_datetime(valeur)
    if date is None:
        return None, False
    if timezone.is_naive(date):
        date = timezone.make_aware(date)
    return date, True


@require_POST
def modifier_statut_candidature(request, pk):
    exiger_droit(request.user, "recrutements", "modification")
    candidature = get_object_or_404(Candidature, pk=pk)
    if request.POST.get("retour") == "detail":
        retour = redirect("core:detail_candidature", pk=candidature.pk)
    else:
        retour = redirect("core:candidatures_offre", pk=candidature.offre_id)

    statut = request.POST.get("statut")
    if statut not in dict(candidature._meta.get_field("statut").choices):
        messages.error(request, "Statut de candidature invalide.")
        return retour
    if candidature.recrute and statut == StatutCandidature.REJETEE:
        messages.error(request, "Ce candidat est déjà recruté : son statut ne peut plus être « Refusée ».")
        return retour

    candidature.statut = statut
    champs = ["statut"]
    for champ in ("date_entretien", "date_entretien_technique"):
        date, valide = _lire_date(request, champ)
        if not valide:
            messages.error(request, "Date d'entretien invalide.")
            return retour
        if date is not None:
            setattr(candidature, champ, date)
            champs.append(champ)
    candidature.save(update_fields=champs)
    log_activity(
        request.user,
        "Mise a jour du statut d'une candidature",
        f"Candidature {candidature.email} : {candidature.get_statut_display()}.",
    )
    messages.success(request, "Statut de candidature mis à jour.")
    return retour


@require_POST
def recruter_candidat(request, pk):
    """BF-RH-16 : enregistre le candidat comme effectivement recrute (sans creer de compte)."""
    exiger_droit(request.user, "recrutements", "modification")
    candidature = get_object_or_404(Candidature, pk=pk)
    retour = redirect("core:detail_candidature", pk=candidature.pk) if request.POST.get("retour") == "detail" \
        else redirect("core:candidatures_offre", pk=candidature.offre_id)
    if candidature.statut == StatutCandidature.REJETEE:
        messages.error(request, "Une candidature refusée ne peut pas être recrutée : changez d'abord son statut.")
        return retour
    if not candidature.recrute:
        candidature.recrute = True
        candidature.statut = StatutCandidature.RETENUE
        candidature.date_recrutement = timezone.now()
        candidature.save(update_fields=["recrute", "statut", "date_recrutement"])
        log_activity(
            request.user,
            "Recrutement d'un candidat",
            f"{candidature.nom_candidat} recrute pour l'offre {candidature.offre.poste}.",
        )
        messages.success(request, f"{candidature.nom_candidat} est enregistré comme recruté.")
    return retour
