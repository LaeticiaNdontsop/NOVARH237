from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from accounts.mixins import droit_requis
from employees.models import Employe
from . import indicateurs
from .assistant import AssistantIndisponible, repondre
from .contexte_assistant import construire_contexte
from .forms import PredictionAttritionForm, QuestionAssistantForm
from .models import EchangeAssistant, PredictionAttrition
from .prediction import predire_attrition


def _valeurs_initiales_depuis_employe(employe: Employe) -> dict:
    """
    Pre-remplit les quelques variables du modele qui existent reellement dans
    NOVA RH (age, anciennete, service, genre, revenu). Les autres variables
    (issues du questionnaire RH americain d'origine : satisfaction, deplacements,
    heures supplementaires...) ne sont pas collectees par NOVA RH et restent aux
    valeurs par defaut du formulaire, a ajuster manuellement.
    """
    initial = {}
    if employe.date_naissance:
        aujourdhui = date.today()
        age = aujourdhui.year - employe.date_naissance.year - (
            (aujourdhui.month, aujourdhui.day) < (employe.date_naissance.month, employe.date_naissance.day)
        )
        initial["Age"] = age

    if employe.date_embauche:
        anciennete = date.today().year - employe.date_embauche.year
        initial["YearsAtCompany"] = max(anciennete, 0)
        initial["TotalWorkingYears"] = max(anciennete, 0)

    if employe.sexe == "H":
        initial["Gender"] = "Male"
    elif employe.sexe == "F":
        initial["Gender"] = "Female"

    derniere_remuneration = employe.remunerations.first()
    if derniere_remuneration:
        initial["MonthlyIncome"] = int(derniere_remuneration.total)

    # Le service NOVA RH est un texte libre : on tente une correspondance simple
    # avec les 3 departements connus du modele, sinon on laisse la valeur par defaut.
    service = (employe.service or "").strip().lower()
    if "rh" in service or "human" in service or "ressources humaines" in service:
        initial["Department"] = "Human Resources"
    elif "vente" in service or "sales" in service or "commercial" in service:
        initial["Department"] = "Sales"
    elif "recherche" in service or "développement" in service or "developpement" in service or "r&d" in service:
        initial["Department"] = "Research & Development"

    return initial


class PredictionAttritionView(droit_requis("analyse", "lecture", "lecture"), View):
    """
    BF-RH-19 : simulateur de prediction d'attrition. Accessible avec ou sans
    fiche employe associee (auto-remplissage partiel dans ce dernier cas).
    """
    template_name = "analytics/prediction.html"

    def get(self, request, employe_pk=None):
        employe = get_object_or_404(Employe, pk=employe_pk) if employe_pk else None
        initial = _valeurs_initiales_depuis_employe(employe) if employe else {}
        form = PredictionAttritionForm(initial=initial)
        return render(request, self.template_name, {"form": form, "employe": employe, "resultat": None})

    def post(self, request, employe_pk=None):
        employe = get_object_or_404(Employe, pk=employe_pk) if employe_pk else None
        form = PredictionAttritionForm(request.POST)
        resultat = None
        if form.is_valid():
            donnees = form.to_donnees_modele()
            resultat = predire_attrition(donnees)
            PredictionAttrition.objects.create(
                employe=employe,
                demande_par=request.user,
                prediction_depart=bool(resultat["prediction"]),
                probabilite_depart=resultat["probabilite_depart"],
                niveau_risque=resultat["niveau_risque"],
                donnees_utilisees=donnees,
            )
        return render(request, self.template_name, {"form": form, "employe": employe, "resultat": resultat})


class HistoriquePredictionsView(droit_requis("analyse"), ListView):
    """Historique des simulations effectuees (tracabilite RG-13)."""
    model = PredictionAttrition
    template_name = "analytics/historique.html"
    context_object_name = "predictions"
    paginate_by = 20

    def get_queryset(self):
        qs = PredictionAttrition.objects.select_related("employe__utilisateur", "demande_par")
        employe_pk = self.kwargs.get("employe_pk")
        if employe_pk:
            qs = qs.filter(employe_id=employe_pk)
        return qs


# ---------------------------------------------------------------------------
# Tableaux de bord et indicateurs (BF-RH-17 / BF-RH-18, CDC §6.5.9)
# ---------------------------------------------------------------------------
class TableauxBordView(droit_requis("analyse"), TemplateView):
    """
    Vue dediee aux 4 indicateurs du CDC (effectif, absenteisme, turnover, taux
    d'acceptation des conges), separee des tableaux de bord operationnels
    (core:dashboard_admin / core:dashboard_rh) qui, eux, listent les actions du
    jour (demandes a traiter). Non-fonctionnel 8.3 : le calcul reste rapide
    (agregations SQL + une boucle bornee sur les absences du mois), donc pas de
    job asynchrone necessaire a ce stade.
    """
    template_name = "analytics/tableaux_bord.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(indicateurs.indicateurs_tableau_de_bord())
        return ctx


class AnalyseIntelligenteView(droit_requis("analyse"), TemplateView):
    """
    Analyse intelligente : indicateurs REELS par departement (turnover, absenteisme,
    tendance des effectifs) lus avec des regles simples et transparentes. Elle ne
    reprend pas les resultats du modele de prediction experimental, accessible a part.
    """
    template_name = "analytics/analyse.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lignes = indicateurs.analyse_par_departement()
        historique = indicateurs.historique_effectif(6)
        ctx.update({
            "lignes": lignes,
            "courbe": indicateurs.courbe_svg(historique),
            "variation_effectif": indicateurs.variation_effectif(6),
            "turnover": indicateurs.turnover(),
            "absenteisme": indicateurs.taux_absenteisme(),
            "nb_a_surveiller": sum(1 for l in lignes if l["niveau"] in ("Élevé", "Modéré")),
            "nb_eleves": sum(1 for l in lignes if l["niveau"] == "Élevé"),
            "effectif": indicateurs.effectif_actif(),
            "date_analyse": timezone.localtime(),
            "seuils": {
                "turnover_eleve": indicateurs.SEUIL_TURNOVER_ELEVE,
                "turnover_modere": indicateurs.SEUIL_TURNOVER_MODERE,
                "absenteisme_eleve": indicateurs.SEUIL_ABSENTEISME_ELEVE,
                "absenteisme_modere": indicateurs.SEUIL_ABSENTEISME_MODERE,
            },
        })
        return ctx


# ---------------------------------------------------------------------------
# Assistant conversationnel (BF-RH-20, RG-15, CDC §6.5.10)
# ---------------------------------------------------------------------------
class AssistantView(droit_requis("assistant", "lecture", "lecture"), View):
    """
    Accessible a tout utilisateur authentifie (Employe, Responsable RH,
    Administrateur) : RG-15 est appliquee en amont par contexte_assistant.py,
    qui adapte ce que l'assistant "voit" selon le role - pas ici par une
    restriction d'acces a la page elle-meme.

    L'historique de la conversation est garde en session (cote serveur, propre
    a cet utilisateur), pour permettre des questions de suivi sans repartir de
    zero, sans avoir besoin d'un modele de donnees dedie.
    """
    template_name = "analytics/assistant.html"
    CLE_SESSION = "historique_assistant"
    MAX_HISTORIQUE = 6

    def get(self, request):
        form = QuestionAssistantForm()
        historique = request.session.get(self.CLE_SESSION, [])
        return render(request, self.template_name, {"form": form, "historique": historique, "erreur": None})

    def post(self, request):
        form = QuestionAssistantForm(request.POST)
        historique = request.session.get(self.CLE_SESSION, [])
        erreur = None

        if "effacer" in request.POST:
            request.session[self.CLE_SESSION] = []
            return render(request, self.template_name, {"form": QuestionAssistantForm(), "historique": [], "erreur": None})

        if form.is_valid():
            question = form.cleaned_data["question"]
            contexte = construire_contexte(request.user)
            try:
                reponse = repondre(question, contexte, historique=historique)
                EchangeAssistant.objects.create(utilisateur=request.user, question=question, reponse=reponse)
                historique.append({"question": question, "reponse": reponse})
                historique = historique[-self.MAX_HISTORIQUE:]
                request.session[self.CLE_SESSION] = historique
                form = QuestionAssistantForm()
            except AssistantIndisponible as exc:
                erreur = str(exc)
                EchangeAssistant.objects.create(
                    utilisateur=request.user, question=question, reponse="", en_erreur=True
                )

        return render(request, self.template_name, {"form": form, "historique": historique, "erreur": erreur})
