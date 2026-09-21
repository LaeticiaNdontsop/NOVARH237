"""Module Formations (BF-RH-11, BF-EMP10, RG-23) : ciblage par le RH et suivi des participations."""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView

from accounts.mixins import droit_requis
from notifications.models import ActivityLog, log_activity, notifier
from .forms import FormationForm
from .models import Formation, ParticipationFormation, StatutParticipation


class HistoriqueFormationsView(droit_requis("formations"), TemplateView):
    template_name = "core/historique_formations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filtre = Q(action__icontains="formation") | Q(details__icontains="formation")
        ctx["historique"] = ActivityLog.objects.filter(filtre).order_by("-date_creation")[:200]
        return ctx


class FormationsView(droit_requis("formations"), TemplateView):
    template_name = "core/formations.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        formations = list(Formation.objects.prefetch_related("participations__employe__utilisateur"))
        recherche = self.request.GET.get("q", "").strip().lower()
        etat = self.request.GET.get("etat", "")
        if recherche:
            formations = [f for f in formations if recherche in f.titre.lower() or recherche in f.description.lower()]
        if etat:
            formations = [f for f in formations if f.etat == etat]
        tous = list(Formation.objects.prefetch_related("participations"))
        prochaine = next((f for f in tous if f.etat in ("Planifiée", "En cours")), None)
        ctx.update({
            "formations": formations,
            "nb_planifiees": sum(1 for f in tous if f.etat == "Planifiée"),
            "nb_participants": ParticipationFormation.objects.values("employe").distinct().count(),
            "nb_terminees": sum(1 for f in tous if f.etat == "Terminée"),
            "prochaine": prochaine,
            "etats": ["Planifiée", "En cours", "Terminée", "Annulée"],
            "recherche": self.request.GET.get("q", ""),
            "etat_filtre": etat,
        })
        return ctx


class _NotifierCiblesMixin:
    def notifier_nouvelles_cibles(self, form):
        formation = self.object
        for employe in form.nouveaux_cibles:
            notifier(
                self.request.user, employe.utilisateur,
                f"Vous êtes concerné(e) par la formation « {formation.titre} » "
                f"le {formation.date_formation:%d/%m/%Y}.",
                categorie="FORMATION",
            )


class CreerFormationView(_NotifierCiblesMixin, droit_requis("formations", "creation", "creation"), CreateView):
    model = Formation
    form_class = FormationForm
    template_name = "core/formation_form.html"
    success_url = reverse_lazy("core:formations")

    def form_valid(self, form):
        form.instance.creee_par = self.request.user
        response = super().form_valid(form)
        self.notifier_nouvelles_cibles(form)
        log_activity(
            self.request.user,
            "Planification d'une formation",
            f"Formation {form.instance.titre} planifiee ({len(form.nouveaux_cibles)} employe(s) cible(s)).",
        )
        messages.success(self.request, "Formation planifiée.")
        return response


class ModifierFormationView(_NotifierCiblesMixin, droit_requis("formations"), UpdateView):
    model = Formation
    form_class = FormationForm
    template_name = "core/formation_form.html"
    success_url = reverse_lazy("core:formations")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.notifier_nouvelles_cibles(form)
        log_activity(
            self.request.user,
            "Modification d'une formation",
            f"Formation {form.instance.titre} modifiee.",
        )
        messages.success(self.request, "Formation mise à jour.")
        return response


class SuiviFormationView(droit_requis("formations"), TemplateView):
    """Suivi de la participation effective des employes cibles."""
    template_name = "core/formation_suivi.html"

    def _formation(self):
        return get_object_or_404(Formation, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        formation = self._formation()
        ctx["formation"] = formation
        ctx["participations"] = formation.participations.select_related("employe__utilisateur")
        ctx["statuts"] = StatutParticipation.choices
        return ctx

    def post(self, request, *args, **kwargs):
        formation = self._formation()
        valides = dict(StatutParticipation.choices)
        modifies = 0
        for participation in formation.participations.all():
            statut = request.POST.get(f"statut_{participation.pk}")
            if statut in valides and statut != participation.statut:
                participation.statut = statut
                participation.save(update_fields=["statut", "date_maj"])
                modifies += 1
        if modifies:
            log_activity(
                request.user,
                "Suivi de participation a une formation",
                f"Formation {formation.titre} : {modifies} participation(s) mise(s) a jour.",
            )
        messages.success(request, "Suivi des participations enregistré.")
        return redirect("core:suivi_formation", pk=formation.pk)
